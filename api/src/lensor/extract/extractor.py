import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from lensor.clauses import CLAUSE_TYPES, canonical_clause_type
from lensor.extract.prompts import CLAUSE_DESCRIPTIONS, excerpt_messages, full_text_messages
from lensor.extract.quotes import locate_quote
from lensor.extract.schema import ClauseResult, ExtractionResult, RiskLevel
from lensor.llm.client import LLMClient, Usage
from lensor.vectorstore.base import ChunkHit

logger = logging.getLogger(__name__)

PROMPT_VERSION = 1
RETRIEVAL_TOP_K = 5

Retrieve = Callable[[str], Awaitable[list[ChunkHit]]]


@dataclass(frozen=True)
class VerifiedClause:
    clause_type: str
    found: bool
    spans: list[tuple[int, int]]
    quotes: list[str]
    summary: str
    risk_level: RiskLevel | None


async def extract_clauses(
    text: str,
    llm: LLMClient,
    model: str,
    mode: Literal["full", "retrieval"] = "full",
    retrieve: Retrieve | None = None,
) -> tuple[list[VerifiedClause], Usage]:
    """Ask the LLM for the 10 clause types, then keep only the quotes that are in the text."""
    if mode == "full":
        messages = full_text_messages(text)
    else:
        if retrieve is None:
            raise ValueError("Retrieval mode needs a retrieve function")
        messages = excerpt_messages(await _excerpts(retrieve))
    result, usage = await llm.complete_json(model, messages, ExtractionResult)
    return _verify(text, result), usage


async def _excerpts(retrieve: Retrieve) -> list[str]:
    seen: set[int] = set()
    excerpts: list[str] = []
    for name in CLAUSE_TYPES:
        for hit in (await retrieve(f"{name}: {CLAUSE_DESCRIPTIONS[name]}"))[:RETRIEVAL_TOP_K]:
            if hit.chunk_id not in seen:
                seen.add(hit.chunk_id)
                excerpts.append(hit.text)
    return excerpts


def _verify(text: str, result: ExtractionResult) -> list[VerifiedClause]:
    by_type: dict[str, ClauseResult] = {}
    for item in result.clauses:
        name = canonical_clause_type(item.clause_type)
        if name is None:
            logger.warning("Dropped an unknown clause type (%d chars)", len(item.clause_type))
        elif name in by_type:
            logger.warning("Dropped duplicate clause type %r", item.clause_type)
        else:
            by_type[name] = item

    clauses = []
    for name in CLAUSE_TYPES:
        chosen = by_type.get(name)
        spans: list[tuple[int, int]] = []
        quotes: list[str] = []
        if chosen is not None and chosen.found:
            for quote in chosen.quotes:
                span = locate_quote(text, quote)
                if span is None:
                    logger.warning(
                        "Dropped a quote that is not in the contract: %s (%d chars)",
                        name,
                        len(quote),
                    )
                elif span not in spans:
                    spans.append(span)
                    quotes.append(text[span[0] : span[1]])
        if spans and chosen is not None:
            clauses.append(
                VerifiedClause(name, True, spans, quotes, chosen.summary, chosen.risk_level)
            )
        else:
            clauses.append(VerifiedClause(name, False, [], [], "", None))
    return clauses
