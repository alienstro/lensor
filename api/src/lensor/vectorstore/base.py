from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: int
    contract_id: int
    start_char: int
    end_char: int
    text: str
    embedding: list[float]


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: int
    contract_id: int
    start_char: int
    end_char: int
    text: str
    score: float  # Cosine similarity: 1.0 is the same direction.


class VectorStore(Protocol):
    async def upsert(self, records: list[ChunkRecord]) -> None: ...

    async def search(
        self, embedding: list[float], top_k: int, contract_ids: list[int] | None = None
    ) -> list[ChunkHit]: ...

    async def delete_contract(self, contract_id: int) -> None: ...
