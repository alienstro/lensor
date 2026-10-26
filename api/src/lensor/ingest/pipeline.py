"""Ingest one contract: parse, chunk, embed, extract, score, and summarize."""

import logging

from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lensor.config import Settings
from lensor.extract.extractor import PROMPT_VERSION, VerifiedClause, extract_clauses
from lensor.extract.risk import risk_score
from lensor.ingest.chunker import chunk_text
from lensor.ingest.parse import parse_document
from lensor.llm.client import LLMClient, LLMError
from lensor.models import Chunk, ClauseExtraction, Contract
from lensor.vectorstore.base import ChunkRecord, VectorStore

logger = logging.getLogger(__name__)

EMBED_BATCH = 64

SessionFactory = async_sessionmaker[AsyncSession]


class Overview(BaseModel):
    overview: str = Field(description="At most 80 words, in plain language.")


async def ingest_contract(
    contract_id: int,
    session_factory: SessionFactory,
    llm: LLMClient,
    store: VectorStore,
    settings: Settings,
    data: bytes | None = None,
    filename: str | None = None,
) -> None:
    """Run the pipeline. On an error, set the status to `failed` with the message.

    `data` and `filename` are the uploaded file. Without them, the stored text is used.
    """
    try:
        await _run(contract_id, session_factory, llm, store, settings, data, filename)
    except (LLMError, ValueError) as exc:
        logger.warning("Ingest of contract %s failed: %s", contract_id, exc)
        await _set_status(session_factory, contract_id, "failed", str(exc))
    except Exception:
        logger.exception("Ingest of contract %s failed", contract_id)
        await _set_status(
            session_factory, contract_id, "failed", "Lensor could not process this contract."
        )


async def _run(
    contract_id: int,
    session_factory: SessionFactory,
    llm: LLMClient,
    store: VectorStore,
    settings: Settings,
    data: bytes | None,
    filename: str | None,
) -> None:
    await _set_status(session_factory, contract_id, "parsing")
    async with session_factory() as session:
        contract = await session.get(Contract, contract_id)
        if contract is None:
            raise ValueError(f"Contract {contract_id} does not exist")
        if data is not None:
            contract.text = parse_document(filename or "upload.txt", data)
        text = contract.text
        if not text.strip():
            raise ValueError("The contract has no text.")
        await session.commit()

    await _set_status(session_factory, contract_id, "chunking")
    async with session_factory() as session:
        # Remove the rows of an earlier run, so that a second run does not add duplicates.
        await store.delete_contract(contract_id)
        await session.execute(delete(Chunk).where(Chunk.contract_id == contract_id))
        await session.execute(
            delete(ClauseExtraction).where(ClauseExtraction.contract_id == contract_id)
        )
        chunks = [
            Chunk(
                contract_id=contract_id, start_char=c.start_char, end_char=c.end_char, text=c.text
            )
            for c in chunk_text(text)
        ]
        session.add_all(chunks)
        await session.commit()

    await _set_status(session_factory, contract_id, "embedding")
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        vectors = await llm.embed([c.text for c in batch])
        await store.upsert(
            [
                ChunkRecord(c.id, contract_id, c.start_char, c.end_char, c.text, vector)
                for c, vector in zip(batch, vectors, strict=True)
            ]
        )

    await _set_status(session_factory, contract_id, "extracting")
    clauses, _ = await extract_clauses(text, llm, settings.llm_model_extract)
    overview, _ = await llm.complete_json(
        settings.llm_model_summary, _overview_messages(clauses), Overview
    )

    async with session_factory() as session:
        session.add_all(_extraction_rows(contract_id, clauses, settings.llm_model_extract))
        contract = await session.get(Contract, contract_id)
        assert contract is not None
        contract.risk_score = risk_score(clauses)
        contract.overview = overview.overview.strip()
        contract.status = "ready"
        contract.status_detail = None
        await session.commit()


def _extraction_rows(
    contract_id: int, clauses: list[VerifiedClause], model: str
) -> list[ClauseExtraction]:
    rows = []
    for clause in clauses:
        common = {
            "contract_id": contract_id,
            "clause_type": clause.clause_type,
            "found": clause.found,
            "summary": clause.summary,
            "risk_level": clause.risk_level,
            "model": model,
            "prompt_version": PROMPT_VERSION,
        }
        if not clause.found:
            rows.append(ClauseExtraction(**common, quote=None, start_char=None, end_char=None))
            continue
        for (start, end), quote in zip(clause.spans, clause.quotes, strict=True):
            rows.append(ClauseExtraction(**common, quote=quote, start_char=start, end_char=end))
    return rows


def _overview_messages(clauses: list[VerifiedClause]) -> list[dict]:
    lines = [
        f"- {c.clause_type}: {c.summary}" if c.found else f"- {c.clause_type}: not found"
        for c in clauses
    ]
    return [
        {
            "role": "system",
            "content": (
                "Write an overview of a contract in at most 80 words, for a person who is not "
                "a lawyer. Use only the clause results below. Do not give legal advice."
            ),
        },
        {"role": "user", "content": "Clause results:\n" + "\n".join(lines)},
    ]


async def _set_status(
    session_factory: SessionFactory, contract_id: int, status: str, detail: str | None = None
) -> None:
    async with session_factory() as session:
        contract = await session.get(Contract, contract_id)
        if contract is None:
            return
        contract.status = status
        contract.status_detail = detail
        await session.commit()
