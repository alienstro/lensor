"""Check the citations in an agent answer against the stored contract text."""

import re
from dataclasses import dataclass

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


async def verify_citations(answer: str, session: AsyncSession) -> list[Citation]:
    """Return each distinct citation in order. A citation is verified when its contract
    exists and its span is a non-empty range inside the contract text."""
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
