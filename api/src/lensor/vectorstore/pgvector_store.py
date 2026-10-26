from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lensor.models import Chunk, ChunkVector
from lensor.vectorstore.base import ChunkHit, ChunkRecord


class PgVectorStore:
    """Stores the vectors in Postgres. The chunk text and offsets come from the `chunks` table."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert(self, records: list[ChunkRecord]) -> None:
        if not records:
            return
        rows = [
            {"chunk_id": r.chunk_id, "contract_id": r.contract_id, "embedding": r.embedding}
            for r in records
        ]
        stmt = insert(ChunkVector).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ChunkVector.chunk_id],
            set_={"embedding": stmt.excluded.embedding, "contract_id": stmt.excluded.contract_id},
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def search(
        self, embedding: list[float], top_k: int, contract_ids: list[int] | None = None
    ) -> list[ChunkHit]:
        distance = ChunkVector.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(Chunk, distance)
            .join(ChunkVector, ChunkVector.chunk_id == Chunk.id)
            .order_by(distance)
            .limit(top_k)
        )
        if contract_ids is not None:
            stmt = stmt.where(ChunkVector.contract_id.in_(contract_ids))
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()
        return [
            ChunkHit(
                chunk_id=chunk.id,
                contract_id=chunk.contract_id,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                text=chunk.text,
                score=1.0 - float(dist),
            )
            for chunk, dist in rows
        ]

    async def delete_contract(self, contract_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(ChunkVector).where(ChunkVector.contract_id == contract_id))
            await session.commit()
