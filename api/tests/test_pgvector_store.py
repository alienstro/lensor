import pytest
from sqlalchemy import func, select

from lensor.models import Chunk, ChunkVector, Contract
from lensor.vectorstore.base import ChunkRecord
from lensor.vectorstore.pgvector_store import PgVectorStore
from tests.fakes import fake_vector

pytestmark = pytest.mark.db


async def seed(session_factory) -> list[ChunkRecord]:
    """Two contracts: contract 1 has chunks a and b, contract 2 has chunk c."""
    records = []
    async with session_factory() as session:
        for title, texts in (("One", ["alpha", "bravo"]), ("Two", ["charlie"])):
            contract = Contract(title=title, source="cuad", text=" ".join(texts), status="ready")
            session.add(contract)
            await session.flush()
            offset = 0
            for text in texts:
                chunk = Chunk(
                    contract_id=contract.id,
                    start_char=offset,
                    end_char=offset + len(text),
                    text=text,
                )
                session.add(chunk)
                await session.flush()
                records.append(
                    ChunkRecord(
                        chunk_id=chunk.id,
                        contract_id=contract.id,
                        start_char=chunk.start_char,
                        end_char=chunk.end_char,
                        text=text,
                        embedding=fake_vector(text),
                    )
                )
                offset += len(text) + 1
        await session.commit()
    return records


async def test_upsert_and_search_orders_by_similarity(session_factory) -> None:
    records = await seed(session_factory)
    store = PgVectorStore(session_factory)
    await store.upsert(records)
    await store.upsert(records)  # A second upsert must not add rows.

    hits = await store.search(fake_vector("bravo"), top_k=3)

    assert [h.text for h in hits][0] == "bravo"
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)
    assert hits[0].score >= hits[1].score >= hits[2].score
    assert (hits[0].start_char, hits[0].end_char) == (6, 11)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ChunkVector)) == 3


async def test_search_filters_contract_ids(session_factory) -> None:
    records = await seed(session_factory)
    store = PgVectorStore(session_factory)
    await store.upsert(records)

    hits = await store.search(fake_vector("bravo"), top_k=5, contract_ids=[records[2].contract_id])

    assert [h.text for h in hits] == ["charlie"]


async def test_delete_contract_removes_vectors(session_factory) -> None:
    records = await seed(session_factory)
    store = PgVectorStore(session_factory)
    await store.upsert(records)

    await store.delete_contract(records[0].contract_id)

    hits = await store.search(fake_vector("alpha"), top_k=5)
    assert [h.text for h in hits] == ["charlie"]
