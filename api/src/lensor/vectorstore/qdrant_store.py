from qdrant_client import AsyncQdrantClient, models

from lensor.vectorstore.base import ChunkHit, ChunkRecord

COLLECTION = "lensor_chunks"


class QdrantStore:
    """Stores the vectors and the chunk text in one Qdrant collection. Point id = chunk id."""

    def __init__(self, client: AsyncQdrantClient, dim: int, collection: str = COLLECTION) -> None:
        self._client = client
        self._dim = dim
        self._collection = collection
        self._ready = False

    async def _ensure_collection(self) -> None:
        if self._ready:
            return
        if not await self._client.collection_exists(self._collection):
            await self._client.create_collection(
                self._collection,
                vectors_config=models.VectorParams(size=self._dim, distance=models.Distance.COSINE),
            )
            await self._client.create_payload_index(
                self._collection, "contract_id", field_schema=models.PayloadSchemaType.INTEGER
            )
        self._ready = True

    async def upsert(self, records: list[ChunkRecord]) -> None:
        if not records:
            return
        await self._ensure_collection()
        await self._client.upsert(
            self._collection,
            points=[
                models.PointStruct(
                    id=r.chunk_id,
                    vector=r.embedding,
                    payload={
                        "contract_id": r.contract_id,
                        "start_char": r.start_char,
                        "end_char": r.end_char,
                        "text": r.text,
                    },
                )
                for r in records
            ],
            wait=True,
        )

    async def search(
        self, embedding: list[float], top_k: int, contract_ids: list[int] | None = None
    ) -> list[ChunkHit]:
        await self._ensure_collection()
        query_filter = None
        if contract_ids is not None:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="contract_id", match=models.MatchAny(any=contract_ids)
                    )
                ]
            )
        response = await self._client.query_points(
            self._collection,
            query=embedding,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        hits = []
        for point in response.points:
            payload = point.payload or {}
            hits.append(
                ChunkHit(
                    chunk_id=int(point.id),
                    contract_id=int(payload["contract_id"]),
                    start_char=int(payload["start_char"]),
                    end_char=int(payload["end_char"]),
                    text=str(payload["text"]),
                    score=float(point.score),
                )
            )
        return hits

    async def delete_contract(self, contract_id: int) -> None:
        await self._ensure_collection()
        await self._client.delete(
            self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="contract_id", match=models.MatchValue(value=contract_id)
                        )
                    ]
                )
            ),
            wait=True,
        )
