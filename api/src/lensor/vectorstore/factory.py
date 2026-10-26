from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lensor.config import Settings
from lensor.vectorstore.base import VectorStore
from lensor.vectorstore.pgvector_store import PgVectorStore


def get_vector_store(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> VectorStore:
    if settings.vector_store == "pgvector":
        return PgVectorStore(session_factory)
    raise ValueError(f"Unknown VECTOR_STORE: {settings.vector_store}")
