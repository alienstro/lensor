import pytest
from sqlalchemy import func, select

from lensor.clauses import CLAUSE_TYPES
from lensor.config import Settings
from lensor.ingest.load_cuad import display_title
from lensor.ingest.pipeline import ingest_contract
from lensor.llm.client import LLMError
from lensor.models import Chunk, ChunkVector, ClauseExtraction, Contract
from lensor.vectorstore.pgvector_store import PgVectorStore
from tests.fakes import FakeLLMClient

TEXT = (
    "DISTRIBUTOR AGREEMENT. This Agreement renews automatically for one year. "
    "Liability for fraud is not capped. " * 3
)

EXTRACTION = {
    "clauses": [
        {
            "clause_type": "Renewal Term",
            "found": True,
            "quotes": ["This Agreement renews automatically for one year."],
            "summary": "It renews each year.",
            "risk_level": "medium",
        },
        {
            "clause_type": "Uncapped Liability",
            "found": True,
            "quotes": ["Liability for fraud is not capped."],
            "summary": "No limit for fraud.",
            "risk_level": "high",
        },
    ]
}

pytestmark = pytest.mark.db


async def add_contract(session_factory, text: str = TEXT) -> int:
    async with session_factory() as session:
        contract = Contract(
            title="Distributor Agreement", source="cuad", text=text, status="queued"
        )
        session.add(contract)
        await session.commit()
        return contract.id


async def test_pipeline_happy_path(session_factory) -> None:
    contract_id = await add_contract(session_factory)
    llm = FakeLLMClient(json_results=[EXTRACTION, {"overview": "A distributor deal."}])

    await ingest_contract(
        contract_id, session_factory, llm, PgVectorStore(session_factory), Settings()
    )

    async with session_factory() as session:
        contract = await session.get(Contract, contract_id)
        assert contract is not None
        assert contract.status == "ready"
        assert contract.status_detail is None
        assert contract.overview == "A distributor deal."
        # Uncapped 30 + no cap 15 + renewal 15.
        assert contract.risk_score == 60
        chunks = await session.scalar(select(func.count()).select_from(Chunk))
        vectors = await session.scalar(select(func.count()).select_from(ChunkVector))
        assert chunks and chunks == vectors
        rows = (await session.scalars(select(ClauseExtraction))).all()
    assert {r.clause_type for r in rows} == set(CLAUSE_TYPES)
    renewal = [r for r in rows if r.clause_type == "Renewal Term"]
    # The quote is three times in the text. The locator keeps the first match.
    assert [(r.found, r.start_char, r.end_char) for r in renewal] == [(True, 23, 72)]
    assert all(r.prompt_version == 1 for r in rows)
    assert llm.json_calls[1]["model"] == Settings().llm_model_summary


async def test_pipeline_parses_uploaded_bytes(session_factory) -> None:
    contract_id = await add_contract(session_factory, text="")
    llm = FakeLLMClient(json_results=[EXTRACTION, {"overview": "o"}])

    await ingest_contract(
        contract_id,
        session_factory,
        llm,
        PgVectorStore(session_factory),
        Settings(),
        data=TEXT.encode(),
        filename="deal.txt",
    )

    async with session_factory() as session:
        contract = await session.get(Contract, contract_id)
        assert contract is not None
        assert (contract.status, contract.text) == ("ready", TEXT)


async def test_pipeline_llm_error_sets_failed(session_factory) -> None:
    contract_id = await add_contract(session_factory)
    llm = FakeLLMClient(json_results=[LLMError("no allowed provider")])

    await ingest_contract(
        contract_id, session_factory, llm, PgVectorStore(session_factory), Settings()
    )

    async with session_factory() as session:
        contract = await session.get(Contract, contract_id)
        assert contract is not None
        assert contract.status == "failed"
        assert "no allowed provider" in (contract.status_detail or "")


async def test_pipeline_empty_upload_sets_failed(session_factory) -> None:
    contract_id = await add_contract(session_factory, text="")

    await ingest_contract(
        contract_id,
        session_factory,
        FakeLLMClient(),
        PgVectorStore(session_factory),
        Settings(),
        data=b"   ",
        filename="blank.txt",
    )

    async with session_factory() as session:
        contract = await session.get(Contract, contract_id)
        assert contract is not None
        assert contract.status == "failed"
        assert "no text" in (contract.status_detail or "")


def test_display_title() -> None:
    assert (
        display_title("LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR AGREEMENT")
        == "Distributor Agreement, Limeenergyco (1999)"
    )
    assert display_title("Plain Title") == "Plain Title"
