"""Read-only tools for the chat agent, in the OpenAI `tools` format."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lensor.clauses import CLAUSE_TYPES, canonical_clause_type
from lensor.extract.risk import risk_level_for
from lensor.extract.schema import RiskLevel
from lensor.llm.client import LLMClient
from lensor.models import ClauseExtraction, Contract
from lensor.vectorstore.base import VectorStore

logger = logging.getLogger(__name__)

VISIBLE_SOURCES = ("cuad", "upload")
MAX_SNIPPET = 800


@dataclass
class ToolContext:
    session_factory: async_sessionmaker[AsyncSession]
    store: VectorStore
    llm: LLMClient


def _clause_type(value: str) -> str:
    name = canonical_clause_type(value)
    if name is None:
        raise ValueError(f"clause_type must be one of: {', '.join(CLAUSE_TYPES)}")
    return name


ClauseTypeName = Annotated[str, AfterValidator(_clause_type)]


class SearchArgs(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    clause_type: ClauseTypeName | None = None
    contract_ids: list[int] | None = Field(default=None, max_length=50)
    top_k: int = Field(default=5, ge=1, le=10)


class ListArgs(BaseModel):
    clause_type: ClauseTypeName
    found: bool
    risk_level: RiskLevel | None = None


class SummaryArgs(BaseModel):
    contract_id: int


class CompareArgs(BaseModel):
    clause_type: ClauseTypeName
    contract_ids: list[int] = Field(min_length=2, max_length=5)


def _function(name: str, description: str, args: type[BaseModel]) -> dict[str, Any]:
    schema = args.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": schema},
    }


TOOLS: list[dict[str, Any]] = [
    _function(
        "search_clauses",
        "Semantic search over the contract text. Returns passages with contract id, title, and "
        "character offsets. Use clause_type to focus the search.",
        SearchArgs,
    ),
    _function(
        "list_contracts_by_clause",
        "List the contracts where a clause type was found (found=true) or not found "
        "(found=false). risk_level filters on the clause risk.",
        ListArgs,
    ),
    _function(
        "get_contract_summary",
        "Get the 10 extracted clauses of one contract, with quotes, offsets, and its risk score.",
        SummaryArgs,
    ),
    _function(
        "compare_clauses",
        "Show one clause type side by side for 2 to 5 contracts, with quotes and offsets.",
        CompareArgs,
    ),
]


async def _visible_contracts(session: AsyncSession, ids: list[int] | None = None) -> list[Contract]:
    stmt = select(Contract).where(Contract.source.in_(VISIBLE_SOURCES), Contract.status == "ready")
    if ids is not None:
        stmt = stmt.where(Contract.id.in_(ids))
    return list((await session.scalars(stmt.order_by(Contract.id))).all())


async def _clauses_for(
    session: AsyncSession, contract_ids: list[int], clause_type: str | None = None
) -> list[ClauseExtraction]:
    stmt = select(ClauseExtraction).where(ClauseExtraction.contract_id.in_(contract_ids))
    if clause_type is not None:
        stmt = stmt.where(ClauseExtraction.clause_type == clause_type)
    return list(
        (await session.scalars(stmt.order_by(ClauseExtraction.start_char.nulls_last()))).all()
    )


def _quotes(rows: list[ClauseExtraction]) -> list[dict[str, Any]]:
    return [
        {"text": r.quote, "start": r.start_char, "end": r.end_char}
        for r in rows
        if r.found and r.start_char is not None
    ]


async def search_clauses(args: SearchArgs, ctx: ToolContext) -> dict[str, Any]:
    query = f"{args.clause_type}: {args.query}" if args.clause_type else args.query
    vector = (await ctx.llm.embed([query]))[0]
    async with ctx.session_factory() as session:
        contracts = {c.id: c for c in await _visible_contracts(session, args.contract_ids)}
    if not contracts:
        return {"results": []}
    hits = await ctx.store.search(vector, args.top_k, list(contracts))
    return {
        "results": [
            {
                "contract_id": h.contract_id,
                "title": contracts[h.contract_id].title,
                "start": h.start_char,
                "end": h.end_char,
                "text": h.text[:MAX_SNIPPET],
                "score": round(h.score, 3),
            }
            for h in hits
        ]
    }


async def list_contracts_by_clause(args: ListArgs, ctx: ToolContext) -> dict[str, Any]:
    async with ctx.session_factory() as session:
        contracts = await _visible_contracts(session)
        rows = await _clauses_for(session, [c.id for c in contracts], args.clause_type)
    found_ids = {r.contract_id for r in rows if r.found}
    risk_by_id = {r.contract_id: r.risk_level for r in rows if r.found}
    has_row = {r.contract_id for r in rows}
    result = []
    for contract in contracts:
        if contract.id not in has_row:
            continue
        if (contract.id in found_ids) != args.found:
            continue
        if args.risk_level is not None and risk_by_id.get(contract.id) != args.risk_level:
            continue
        result.append(
            {"contract_id": contract.id, "title": contract.title, "risk_score": contract.risk_score}
        )
    return {"clause_type": args.clause_type, "found": args.found, "contracts": result}


async def get_contract_summary(args: SummaryArgs, ctx: ToolContext) -> dict[str, Any]:
    async with ctx.session_factory() as session:
        contracts = await _visible_contracts(session, [args.contract_id])
        if not contracts:
            return {"error": f"No contract with id {args.contract_id}."}
        rows = await _clauses_for(session, [args.contract_id])
    contract = contracts[0]
    clauses = []
    for name in CLAUSE_TYPES:
        typed = [r for r in rows if r.clause_type == name]
        quotes = _quotes(typed)
        first = next((r for r in typed if r.found), None)
        clauses.append(
            {
                "clause_type": name,
                "found": bool(quotes),
                "summary": first.summary if first else "",
                "risk_level": first.risk_level if first else None,
                "quotes": quotes,
            }
        )
    score = contract.risk_score
    return {
        "contract_id": contract.id,
        "title": contract.title,
        "risk_score": score,
        "risk_level": risk_level_for(score) if score is not None else None,
        "overview": contract.overview,
        "clauses": clauses,
    }


async def compare_clauses(args: CompareArgs, ctx: ToolContext) -> dict[str, Any]:
    async with ctx.session_factory() as session:
        contracts = await _visible_contracts(session, args.contract_ids)
        rows = await _clauses_for(session, [c.id for c in contracts], args.clause_type)
    by_id = {c.id: c for c in contracts}
    result = []
    for contract_id in args.contract_ids:
        contract = by_id.get(contract_id)
        if contract is None:
            result.append({"contract_id": contract_id, "error": "No contract with this id."})
            continue
        quotes = _quotes([r for r in rows if r.contract_id == contract_id])
        result.append(
            {
                "contract_id": contract_id,
                "title": contract.title,
                "found": bool(quotes),
                "quotes": quotes,
            }
        )
    return {"clause_type": args.clause_type, "contracts": result}


Handler = Callable[[Any, ToolContext], Awaitable[dict[str, Any]]]

_REGISTRY: dict[str, tuple[type[BaseModel], Handler]] = {
    "search_clauses": (SearchArgs, search_clauses),
    "list_contracts_by_clause": (ListArgs, list_contracts_by_clause),
    "get_contract_summary": (SummaryArgs, get_contract_summary),
    "compare_clauses": (CompareArgs, compare_clauses),
}


async def run_tool(name: str, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Run one tool. Return {"error": ...} for bad input or a failure. Never raise."""
    entry = _REGISTRY.get(name)
    if entry is None:
        return {"error": f"Unknown tool {name!r}."}
    model, handler = entry
    try:
        parsed = model.model_validate(args)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return {"error": f"Bad arguments: {details}"}
    try:
        return await handler(parsed, ctx)
    except Exception:
        logger.exception("Tool %s failed", name)
        return {"error": f"The tool {name} failed. Try another approach."}
