from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://lensor:lensor@localhost:5433/lensor"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model_extract: str = "deepseek/deepseek-v4.1-flash"
    # False turns reasoning off: about 3 times cheaper, but recall fell from 0.84 to 0.69.
    llm_extract_reasoning: bool = True
    llm_model_agent: str = "openai/gpt-5-mini"
    llm_model_summary: str = "openai/gpt-5-nano"
    embed_model: str = "openai/text-embedding-3-small"
    embed_dim: int = 1536
    vector_store: Literal["pgvector", "qdrant"] = "pgvector"
    qdrant_url: str = "http://qdrant:6333"
    agent_max_tool_calls: int = 8
    chat_rate_limit: str = "20/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
