from functools import lru_cache

from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lensor.config import Settings
from lensor.vectorstore.base import VectorStore
from lensor.vectorstore.pgvector_store import PgVectorStore
from lensor.vectorstore.qdrant_store import QdrantStore


@lru_cache
def _qdrant_client(url: str) -> AsyncQdrantClient:
    return AsyncQdrantClient(url=url)


def get_vector_store(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> VectorStore:
    """VECTOR_STORE selects the store. Only one store runs at a time."""
    if settings.vector_store == "qdrant":
        return QdrantStore(_qdrant_client(settings.qdrant_url), dim=settings.embed_dim)
    return PgVectorStore(session_factory)
