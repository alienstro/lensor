import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lensor.clauses import CLAUSE_TYPES
from lensor.deps import LLMDep, SessionFactoryDep, SettingsDep, StoreDep
from lensor.extract.risk import risk_level_for, risk_reasons
from lensor.ingest.pipeline import ingest_contract
from lensor.models import ClauseExtraction, Contract
from lensor.sse import SSE_HEADERS, sse_event

router = APIRouter(prefix="/api/contracts")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".txt"}
STATUS_POLL_SECONDS = 1.0
FINAL_STATUSES = {"ready", "failed"}
# Rows with source "eval" are temporary copies that the evaluation CLI makes.
VISIBLE_SOURCES = ("cuad", "upload")


class _FoundClause:
    def __init__(self, clause_type: str, found: bool) -> None:
        self.clause_type = clause_type
        self.found = found


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(stem.split()).title()[:300] or "Uploaded contract"


def _summary(contract: Contract, found_types: set[str]) -> dict[str, Any]:
    reasons = risk_reasons(_FoundClause(name, name in found_types) for name in CLAUSE_TYPES)
    ready = contract.status == "ready" and contract.risk_score is not None
    return {
        "id": contract.id,
        "title": contract.title,
        "source": contract.source,
        "status": contract.status,
        "risk_score": contract.risk_score,
        "risk_level": risk_level_for(contract.risk_score) if ready else None,  # type: ignore[arg-type]
        "reasons": [vars(r) for r in reasons] if ready else [],
        "created_at": contract.created_at.isoformat()
        if isinstance(contract.created_at, datetime)
        else None,
    }


async def _found_types(session: AsyncSession, contract_ids: list[int]) -> dict[int, set[str]]:
    rows = await session.execute(
        select(ClauseExtraction.contract_id, ClauseExtraction.clause_type)
        .where(ClauseExtraction.contract_id.in_(contract_ids), ClauseExtraction.found.is_(True))
        .distinct()
    )
    found: dict[int, set[str]] = {cid: set() for cid in contract_ids}
    for contract_id, clause_type in rows:
        found[contract_id].add(clause_type)
    return found


@router.post("", status_code=201)
async def upload_contract(
    file: UploadFile,
    background: BackgroundTasks,
    session_factory: SessionFactoryDep,
    llm: LLMDep,
    store: StoreDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    filename = file.filename or "upload"
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(415, "Lensor reads only PDF and TXT files.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The file is larger than 10 MB.")
    if not data.strip():
        raise HTTPException(400, "The file is empty.")

    async with session_factory() as session:
        contract = Contract(
            title=_title_from_filename(filename), source="upload", text="", status="queued"
        )
        session.add(contract)
        await session.commit()
        contract_id = contract.id

    background.add_task(
        ingest_contract,
        contract_id,
        session_factory,
        llm,
        store,
        settings,
        data=data,
        filename=filename,
    )
    return {"id": contract_id, "status": "queued"}


@router.get("")
async def list_contracts(
    session_factory: SessionFactoryDep,
) -> list[dict[str, Any]]:
    async with session_factory() as session:
        contracts = (
            await session.scalars(
                select(Contract)
                .where(Contract.source.in_(VISIBLE_SOURCES))
                .order_by(Contract.risk_score.desc().nulls_last(), Contract.created_at.desc())
            )
        ).all()
        found = await _found_types(session, [c.id for c in contracts])
    return [_summary(c, found[c.id]) for c in contracts]


@router.get("/{contract_id}")
async def get_contract(contract_id: int, session_factory: SessionFactoryDep) -> dict[str, Any]:
    async with session_factory() as session:
        contract = await session.get(Contract, contract_id)
        if contract is None:
            raise HTTPException(404, "Lensor has no contract with this id.")
        rows = (
            await session.scalars(
                select(ClauseExtraction)
                .where(ClauseExtraction.contract_id == contract_id)
                .order_by(ClauseExtraction.start_char.nulls_last(), ClauseExtraction.id)
            )
        ).all()

    by_type: dict[str, list[ClauseExtraction]] = {}
    for row in rows:
        by_type.setdefault(row.clause_type, []).append(row)
    clauses = []
    for name in CLAUSE_TYPES:
        found_rows = [r for r in by_type.get(name, []) if r.found and r.start_char is not None]
        first = found_rows[0] if found_rows else None
        clauses.append(
            {
                "clause_type": name,
                "found": first is not None,
                "quotes": [r.quote for r in found_rows],
                "spans": [[r.start_char, r.end_char] for r in found_rows],
                "summary": first.summary if first else "",
                "risk_level": first.risk_level if first else None,
            }
        )
    found_types = {str(c["clause_type"]) for c in clauses if c["found"]}
    return {
        **_summary(contract, found_types),
        "text": contract.text,
        "overview": contract.overview,
        "status_detail": contract.status_detail,
        "clauses": clauses,
    }


@router.get("/{contract_id}/status")
async def contract_status(
    contract_id: int, session_factory: SessionFactoryDep
) -> StreamingResponse:
    async with session_factory() as session:
        if await session.get(Contract, contract_id) is None:
            raise HTTPException(404, "Lensor has no contract with this id.")

    async def events() -> AsyncIterator[str]:
        last: tuple[str, str | None] | None = None
        while True:
            async with session_factory() as session:
                contract = await session.get(Contract, contract_id)
            if contract is None:
                return
            current = (contract.status, contract.status_detail)
            if current != last:
                last = current
                yield sse_event({"status": contract.status, "detail": contract.status_detail})
            if contract.status in FINAL_STATUSES:
                return
            await asyncio.sleep(STATUS_POLL_SECONDS)

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)
