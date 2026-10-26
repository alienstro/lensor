import pytest
from qdrant_client import AsyncQdrantClient

from lensor.vectorstore.base import ChunkRecord
from lensor.vectorstore.qdrant_store import QdrantStore
from tests.fakes import fake_vector

DIM = 16


def records() -> list[ChunkRecord]:
    """Contract 1 has chunks alpha and bravo. Contract 2 has chunk charlie."""
    rows = [(1, 1, 0, "alpha"), (2, 1, 6, "bravo"), (3, 2, 0, "charlie")]
    return [
        ChunkRecord(cid, contract, start, start + len(text), text, fake_vector(text, DIM))
        for cid, contract, start, text in rows
    ]


def make_store() -> QdrantStore:
    return QdrantStore(AsyncQdrantClient(location=":memory:"), dim=DIM)


async def test_upsert_and_search_orders_by_similarity() -> None:
    store = make_store()
    await store.upsert(records())
    await store.upsert(records())  # A second upsert must not add points.

    hits = await store.search(fake_vector("bravo", DIM), top_k=3)

    assert len(hits) == 3
    assert hits[0].text == "bravo"
    assert hits[0].score == pytest.approx(1.0, abs=1e-5)
    assert hits[0].score >= hits[1].score >= hits[2].score
    assert (hits[0].chunk_id, hits[0].contract_id, hits[0].start_char, hits[0].end_char) == (
        2,
        1,
        6,
        11,
    )


async def test_search_filters_contract_ids() -> None:
    store = make_store()
    await store.upsert(records())

    hits = await store.search(fake_vector("bravo", DIM), top_k=5, contract_ids=[2])

    assert [h.text for h in hits] == ["charlie"]


async def test_delete_contract_removes_vectors() -> None:
    store = make_store()
    await store.upsert(records())

    await store.delete_contract(1)

    hits = await store.search(fake_vector("alpha", DIM), top_k=5)
    assert [h.text for h in hits] == ["charlie"]


async def test_search_on_empty_store_returns_nothing() -> None:
    assert await make_store().search(fake_vector("x", DIM), top_k=5) == []


def test_factory_selects_the_store() -> None:
    from lensor.config import Settings
    from lensor.vectorstore.factory import get_vector_store
    from lensor.vectorstore.pgvector_store import PgVectorStore

    pg = get_vector_store(Settings(vector_store="pgvector"), session_factory=None)  # type: ignore[arg-type]
    qd = get_vector_store(Settings(vector_store="qdrant"), session_factory=None)  # type: ignore[arg-type]

    assert isinstance(pg, PgVectorStore)
    assert isinstance(qd, QdrantStore)
