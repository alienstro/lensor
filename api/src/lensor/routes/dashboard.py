from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from lensor.clauses import CLAUSE_TYPES
from lensor.deps import SessionFactoryDep
from lensor.extract.risk import risk_level_for
from lensor.models import ClauseExtraction, Contract

router = APIRouter()

VISIBLE_SOURCES = ("cuad", "upload")
TOP_RISK = 5


@router.get("/api/dashboard")
async def dashboard(session_factory: SessionFactoryDep) -> dict[str, Any]:
    """Counts over the contracts with status `ready`."""
    async with session_factory() as session:
        contracts = (
            await session.scalars(
                select(Contract)
                .where(Contract.status == "ready", Contract.source.in_(VISIBLE_SOURCES))
                .order_by(Contract.risk_score.desc().nulls_last(), Contract.id)
            )
        ).all()
        rows = (
            await session.execute(
                select(
                    ClauseExtraction.contract_id,
                    ClauseExtraction.clause_type,
                    ClauseExtraction.risk_level,
                )
                .where(
                    ClauseExtraction.contract_id.in_([c.id for c in contracts]),
                    ClauseExtraction.found.is_(True),
                )
                .order_by(ClauseExtraction.id)
            )
        ).all()

    by_level = {"high": 0, "medium": 0, "low": 0}
    for contract in contracts:
        by_level[risk_level_for(contract.risk_score or 0)] += 1

    # One risk level for each (contract, clause type): the first found row.
    clause_risk: dict[tuple[int, str], str | None] = {}
    for contract_id, clause_type, risk_level in rows:
        clause_risk.setdefault((contract_id, clause_type), risk_level)
    by_clause = []
    for name in CLAUSE_TYPES:
        levels = [risk for (_, clause_type), risk in clause_risk.items() if clause_type == name]
        by_clause.append(
            {
                "clause_type": name,
                "found": len(levels),
                "high": levels.count("high"),
                "medium": levels.count("medium"),
                "low": levels.count("low"),
            }
        )
    return {
        "contracts": len(contracts),
        "by_level": by_level,
        "by_clause": by_clause,
        "top_risk": [
            {"id": c.id, "title": c.title, "risk_score": c.risk_score} for c in contracts[:TOP_RISK]
        ],
    }
