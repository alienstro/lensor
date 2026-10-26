import pytest

from lensor.agent.citations import verify_citations
from lensor.agent.tools import TOOLS, ToolContext, run_tool
from lensor.models import Chunk, ClauseExtraction, Contract
from lensor.vectorstore.base import ChunkRecord
from lensor.vectorstore.pgvector_store import PgVectorStore
from tests.fakes import FakeLLMClient, fake_vector

TEXT = "This Agreement renews automatically for one year. Fraud liability is not capped."


def test_tools_are_openai_functions() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert names == {
        "search_clauses",
        "list_contracts_by_clause",
        "get_contract_summary",
        "compare_clauses",
    }
    assert all(t["type"] == "function" for t in TOOLS)


async def test_run_tool_validates_args() -> None:
    ctx = ToolContext(session_factory=None, store=None, llm=FakeLLMClient())  # type: ignore[arg-type]

    unknown = await run_tool("delete_everything", {}, ctx)
    bad_type = await run_tool(
        "list_contracts_by_clause", {"clause_type": "Price", "found": True}, ctx
    )
    too_many = await run_tool(
        "compare_clauses", {"clause_type": "Renewal Term", "contract_ids": [1, 2, 3, 4, 5, 6]}, ctx
    )
    too_few = await run_tool(
        "compare_clauses", {"clause_type": "Renewal Term", "contract_ids": [1]}, ctx
    )

    for result in (unknown, bad_type, too_many, too_few):
        assert set(result) == {"error"}


async def seed(session_factory) -> tuple[int, int]:
    async with session_factory() as session:
        risky = Contract(title="Risky", source="cuad", text=TEXT, status="ready", risk_score=60)
        calm = Contract(title="Calm", source="cuad", text="Short.", status="ready", risk_score=15)
        hidden = Contract(title="Eval copy", source="eval", text=TEXT, status="ready")
        session.add_all([risky, calm, hidden])
        await session.flush()
        common = {"model": "m", "prompt_version": 1}
        session.add_all(
            [
                ClauseExtraction(
                    contract_id=risky.id,
                    clause_type="Renewal Term",
                    found=True,
                    quote=TEXT[:49],
                    start_char=0,
                    end_char=49,
                    summary="Renews.",
                    risk_level="medium",
                    **common,
                ),
                ClauseExtraction(
                    contract_id=calm.id,
                    clause_type="Renewal Term",
                    found=False,
                    summary="",
                    **common,
                ),
                ClauseExtraction(
                    contract_id=hidden.id,
                    clause_type="Renewal Term",
                    found=True,
                    quote=TEXT[:49],
                    start_char=0,
                    end_char=49,
                    summary="Renews.",
                    risk_level="medium",
                    **common,
                ),
            ]
        )
        chunk = Chunk(contract_id=risky.id, start_char=0, end_char=len(TEXT), text=TEXT)
        session.add(chunk)
        await session.commit()
        records = [ChunkRecord(chunk.id, risky.id, 0, len(TEXT), TEXT, fake_vector(TEXT))]
    await PgVectorStore(session_factory).upsert(records)
    return risky.id, calm.id


@pytest.mark.db
async def test_list_contracts_by_clause(session_factory) -> None:
    risky_id, calm_id = await seed(session_factory)
    ctx = ToolContext(session_factory, PgVectorStore(session_factory), FakeLLMClient())

    found = await run_tool(
        "list_contracts_by_clause", {"clause_type": "renewal term", "found": True}, ctx
    )
    missing = await run_tool(
        "list_contracts_by_clause", {"clause_type": "Renewal Term", "found": False}, ctx
    )
    high = await run_tool(
        "list_contracts_by_clause",
        {"clause_type": "Renewal Term", "found": True, "risk_level": "high"},
        ctx,
    )

    assert [c["contract_id"] for c in found["contracts"]] == [risky_id]
    assert [c["contract_id"] for c in missing["contracts"]] == [calm_id]
    assert high["contracts"] == []


@pytest.mark.db
async def test_summary_compare_and_search(session_factory) -> None:
    risky_id, calm_id = await seed(session_factory)
    ctx = ToolContext(session_factory, PgVectorStore(session_factory), FakeLLMClient())

    summary = await run_tool("get_contract_summary", {"contract_id": risky_id}, ctx)
    compared = await run_tool(
        "compare_clauses", {"clause_type": "Renewal Term", "contract_ids": [risky_id, calm_id]}, ctx
    )
    search = await run_tool("search_clauses", {"query": TEXT}, ctx)
    absent = await run_tool("get_contract_summary", {"contract_id": 999999}, ctx)

    assert summary["title"] == "Risky"
    assert len(summary["clauses"]) == 10
    renewal = summary["clauses"][1]
    assert renewal["quotes"] == [{"text": TEXT[:49], "start": 0, "end": 49}]
    assert [c["found"] for c in compared["contracts"]] == [True, False]
    assert search["results"][0]["contract_id"] == risky_id
    assert search["results"][0]["title"] == "Risky"
    assert "error" in absent


@pytest.mark.db
async def test_verify_citations_bad_refs(session_factory) -> None:
    risky_id, _ = await seed(session_factory)
    answer = (
        f"It renews [c:{risky_id}:0-49]. Again [c:{risky_id}:0-49]. "
        f"Unknown [c:999999:0-10]. Past the end [c:{risky_id}:10-5000]. "
        f"Empty [c:{risky_id}:20-20]."
    )

    async with session_factory() as session:
        citations = await verify_citations(answer, session)

    assert [(c.contract_id, c.start, c.end, c.verified) for c in citations] == [
        (risky_id, 0, 49, True),
        (999999, 0, 10, False),
        (risky_id, 10, 5000, False),
        (risky_id, 20, 20, False),
    ]
    assert citations[0].title == "Risky"
    assert citations[0].quote == TEXT[:49]
    assert citations[1].quote is None
