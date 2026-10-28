from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from lensor.clauses import CLAUSE_TYPES
from lensor.deps import SessionFactoryDep
from lensor.models import EvalResult, EvalRun

router = APIRouter()

FINISHED = ("done", "partial")


@router.get("/api/eval/runs/latest")
async def latest_eval_run(session_factory: SessionFactoryDep) -> dict[str, Any]:
    async with session_factory() as session:
        run = await session.scalar(
            select(EvalRun).where(EvalRun.status.in_(FINISHED)).order_by(EvalRun.id.desc()).limit(1)
        )
        if run is None:
            raise HTTPException(404, "No evaluation run yet.")
        results = (
            await session.scalars(select(EvalResult).where(EvalResult.run_id == run.id))
        ).all()
    order = {name: i for i, name in enumerate(CLAUSE_TYPES)}
    return {
        "run": {
            "id": run.id,
            "started_at": run.started_at.isoformat(),
            "model": run.model,
            "mode": run.mode,
            "prompt_version": run.prompt_version,
            "contract_count": run.contract_count,
            "cost_usd": run.cost_usd,
            "status": run.status,
        },
        "results": [
            {
                "clause_type": r.clause_type,
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "recall_at_5": r.recall_at_5,
            }
            for r in sorted(results, key=lambda r: order.get(r.clause_type, len(order)))
        ],
    }
