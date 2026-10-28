"""Check the citations in an agent answer against the stored contract text."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lensor.models import Contract

CITATION_RE = re.compile(r"\[c:(\d+):(\d+)-(\d+)\]")
VISIBLE_SOURCES = ("cuad", "upload")
MAX_CITED_CHARS = 4000


@dataclass(frozen=True)
class Citation:
    contract_id: int
    start: int
    end: int
    verified: bool
    title: str | None
    quote: str | None


Spans = Mapping[int, list[tuple[int, int]]]


def collect_spans(
    result: Any, seen: dict[int, list[tuple[int, int]]], contract_id: int | None = None
) -> None:
    """Add each (start, end) span in a tool result to `seen`, by contract id."""
    if isinstance(result, list):
        for item in result:
            collect_spans(item, seen, contract_id)
        return
    if not isinstance(result, dict):
        return
    if isinstance(result.get("contract_id"), int):
        contract_id = result["contract_id"]
    start, end = result.get("start"), result.get("end")
    if contract_id is not None and isinstance(start, int) and isinstance(end, int):
        seen.setdefault(contract_id, []).append((start, end))
    for value in result.values():
        if isinstance(value, dict | list):
            collect_spans(value, seen, contract_id)


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in spans)


async def verify_citations(
    answer: str, session: AsyncSession, seen: Spans | None = None
) -> list[Citation]:
    """Return each distinct citation in order. A citation is verified when its contract
    exists, its span is a non-empty range inside the contract text, and, when `seen` is given,
    the span overlaps a span that a tool returned for that contract."""
    refs: list[tuple[int, int, int]] = []
    for match in CITATION_RE.finditer(answer):
        ref = (int(match[1]), int(match[2]), int(match[3]))
        if ref not in refs:
            refs.append(ref)
    if not refs:
        return []
    ids = sorted({r[0] for r in refs})
    rows = await session.scalars(
        select(Contract).where(Contract.id.in_(ids), Contract.source.in_(VISIBLE_SOURCES))
    )
    contracts = {c.id: c for c in rows}
    citations = []
    for contract_id, start, end in refs:
        contract = contracts.get(contract_id)
        ok = (
            contract is not None
            and 0 <= start < end <= len(contract.text)
            and end - start <= MAX_CITED_CHARS
            and (seen is None or _overlaps((start, end), list(seen.get(contract_id, []))))
        )
        citations.append(
            Citation(
                contract_id=contract_id,
                start=start,
                end=end,
                verified=ok,
                title=contract.title if contract else None,
                quote=contract.text[start:end] if ok and contract else None,
            )
        )
    return citations
