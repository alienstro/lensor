from pathlib import Path

import pytest
from sqlalchemy import func, select

from lensor.eval.__main__ import run_eval
from lensor.ingest.cuad import load_cuad
from lensor.llm.client import LLMError
from lensor.models import Contract, EvalResult, EvalRun
from lensor.vectorstore.pgvector_store import PgVectorStore
from tests.fakes import FakeLLMClient

pytestmark = pytest.mark.db

MINI = Path(__file__).parent / "fixtures" / "cuad_mini.json"


def item(name: str, quotes: list[str]) -> dict:
    return {
        "clause_type": name,
        "found": True,
        "quotes": quotes,
        "summary": "s",
        "risk_level": "low",
    }


ACME = {
    "clauses": [
        item("Renewal Term", ["This Agreement renews for one year."]),
        item("Governing Law", ["SUPPLY AGREEMENT."]),  # A wrong span: fp and fn.
    ]
}
BETA = {"clauses": [item("Uncapped Liability", ["Liability for fraud is not capped."])]}


async def results(session_factory, run_id: int) -> dict[str, EvalResult]:
    async with session_factory() as session:
        rows = (await session.scalars(select(EvalResult).where(EvalResult.run_id == run_id))).all()
    return {r.clause_type: r for r in rows}


async def test_run_eval_writes_results(session_factory) -> None:
    llm = FakeLLMClient(json_results=[ACME, BETA])

    run_id = await run_eval(
        load_cuad(MINI), llm, "m", "full", session_factory, PgVectorStore(session_factory)
    )

    async with session_factory() as session:
        run = await session.get(EvalRun, run_id)
        assert run is not None
        assert (run.status, run.contract_count, run.mode, run.model) == ("done", 2, "full", "m")
        assert run.cost_usd == pytest.approx(0.002)
        leftover = await session.scalar(
            select(func.count()).select_from(Contract).where(Contract.source == "eval")
        )
        assert leftover == 0
    by_type = await results(session_factory, run_id)
    assert len(by_type) == 10
    assert (by_type["Renewal Term"].precision, by_type["Renewal Term"].recall) == (1.0, 1.0)
    assert (by_type["Governing Law"].precision, by_type["Governing Law"].recall) == (0.0, 0.0)
    # Beta has two Cap on Liability labels and no prediction: one fn.
    assert by_type["Cap on Liability"].recall == 0.0
    assert by_type["Uncapped Liability"].f1 == 1.0
    assert by_type["Renewal Term"].recall_at_5 is None


async def test_run_eval_marks_failed_on_llm_error(session_factory) -> None:
    llm = FakeLLMClient(json_results=[LLMError("rate limited"), BETA])

    run_id = await run_eval(
        load_cuad(MINI), llm, "m", "full", session_factory, PgVectorStore(session_factory)
    )

    async with session_factory() as session:
        run = await session.get(EvalRun, run_id)
        assert run is not None
        assert run.status == "partial"
    by_type = await results(session_factory, run_id)
    assert by_type["Uncapped Liability"].f1 == 1.0


async def test_run_eval_retrieval_check_fills_recall_at_5(session_factory) -> None:
    llm = FakeLLMClient(json_results=[ACME, BETA])

    run_id = await run_eval(
        load_cuad(MINI),
        llm,
        "m",
        "full",
        session_factory,
        PgVectorStore(session_factory),
        retrieval_check=True,
    )

    by_type = await results(session_factory, run_id)
    # Each mini contract is one chunk, so the first hit always overlaps the labels.
    assert by_type["Renewal Term"].recall_at_5 == 1.0
    assert by_type["Expiration Date"].recall_at_5 is None
