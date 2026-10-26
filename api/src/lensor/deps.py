"""FastAPI dependencies. Tests replace them with app.dependency_overrides."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lensor import db
from lensor.config import Settings, get_settings
from lensor.llm.client import LLMClient, OpenRouterClient
from lensor.vectorstore.base import VectorStore
from lensor.vectorstore.factory import get_vector_store


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return db.get_session_factory()


@lru_cache
def _openrouter() -> OpenRouterClient:
    return OpenRouterClient(get_settings())


def get_llm() -> LLMClient:
    return _openrouter()


SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]


def get_store(session_factory: SessionFactoryDep, settings: SettingsDep) -> VectorStore:
    return get_vector_store(settings, session_factory)


StoreDep = Annotated[VectorStore, Depends(get_store)]
