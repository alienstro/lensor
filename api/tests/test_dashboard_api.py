import pytest

from lensor.clauses import CLAUSE_TYPES
from lensor.models import ClauseExtraction, Contract, EvalResult, EvalRun

pytestmark = pytest.mark.db


def found(contract_id: int, name: str, risk: str) -> ClauseExtraction:
    return ClauseExtraction(
        contract_id=contract_id,
        clause_type=name,
        found=True,
        quote="q",
        start_char=0,
        end_char=1,
        summary="s",
        risk_level=risk,
        model="m",
        prompt_version=1,
    )


async def seed(session_factory) -> list[int]:
    async with session_factory() as session:
        rows = [
            Contract(title="High", source="cuad", text="t", status="ready", risk_score=70),
            Contract(title="Medium", source="upload", text="t", status="ready", risk_score=45),
            Contract(title="Low", source="cuad", text="t", status="ready", risk_score=15),
            Contract(title="Queued", source="upload", text="", status="queued"),
            Contract(title="Eval copy", source="eval", text="t", status="ready", risk_score=99),
        ]
        session.add_all(rows)
        await session.flush()
        high, medium, low, _, hidden = rows
        session.add_all(
            [
                found(high.id, "Renewal Term", "high"),
                found(high.id, "Renewal Term", "high"),  # Two quotes count once.
                found(high.id, "Uncapped Liability", "high"),
                found(medium.id, "Renewal Term", "medium"),
                found(hidden.id, "Renewal Term", "low"),
            ]
        )
        await session.commit()
        return [r.id for r in rows]


async def test_dashboard_counts(api, session_factory) -> None:
    ids = await seed(session_factory)

    body = (await api.get("/api/dashboard")).json()

    assert body["contracts"] == 3
    assert body["by_level"] == {"high": 1, "medium": 1, "low": 1}
    by_clause = {row["clause_type"]: row for row in body["by_clause"]}
    assert [row["clause_type"] for row in body["by_clause"]] == list(CLAUSE_TYPES)
    assert by_clause["Renewal Term"] == {
        "clause_type": "Renewal Term",
        "found": 2,
        "high": 1,
        "medium": 1,
        "low": 0,
    }
    assert by_clause["Uncapped Liability"]["found"] == 1
    assert by_clause["Non-Compete"]["found"] == 0
    assert [c["id"] for c in body["top_risk"]] == ids[:3]


async def test_list_hides_eval_contracts(api, session_factory) -> None:
    await seed(session_factory)

    titles = [c["title"] for c in (await api.get("/api/contracts")).json()]

    assert "Eval copy" not in titles
    assert titles[:3] == ["High", "Medium", "Low"]


async def test_eval_latest_404_then_ok(api, session_factory) -> None:
    missing = await api.get("/api/eval/runs/latest")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "No evaluation run yet."

    async with session_factory() as session:
        old = EvalRun(
            model="old",
            mode="full",
            prompt_version=1,
            contract_count=50,
            cost_usd=1.0,
            status="done",
        )
        new = EvalRun(
            model="new",
            mode="retrieval",
            prompt_version=1,
            contract_count=50,
            cost_usd=0.4,
            status="done",
        )
        running = EvalRun(
            model="busy",
            mode="full",
            prompt_version=1,
            contract_count=50,
            cost_usd=0,
            status="running",
        )
        session.add_all([old, new])
        await session.flush()
        session.add(running)
        session.add_all(
            [
                EvalResult(
                    run_id=new.id,
                    clause_type=name,
                    precision=0.8,
                    recall=0.7,
                    f1=0.75,
                    recall_at_5=None,
                )
                for name in reversed(CLAUSE_TYPES)
            ]
        )
        await session.commit()

    body = (await api.get("/api/eval/runs/latest")).json()

    assert body["run"]["model"] == "new"
    assert body["run"]["cost_usd"] == 0.4
    assert "started_at" in body["run"]
    assert [r["clause_type"] for r in body["results"]] == list(CLAUSE_TYPES)
    assert body["results"][0]["f1"] == 0.75
