from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBED_DIM = 1536

# Pipeline status values, in order. "failed" can follow any of them.
CONTRACT_STATUSES = (
    "queued",
    "parsing",
    "chunking",
    "embedding",
    "extracting",
    "ready",
    "failed",
)


class Base(DeclarativeBase):
    pass


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(10))  # "cuad" or "upload"
    text: Mapped[str] = mapped_column(Text, default="")
    overview: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    status_detail: Mapped[str | None] = mapped_column(Text)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    start_char: Mapped[int] = mapped_column(Integer)
    end_char: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class ClauseExtraction(Base):
    """One row for each verified quote. A type with no verified quote has one row with found=False."""

    __tablename__ = "clause_extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    clause_type: Mapped[str] = mapped_column(String(60))
    found: Mapped[bool] = mapped_column(Boolean)
    quote: Mapped[str | None] = mapped_column(Text)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str | None] = mapped_column(String(10))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[int] = mapped_column(Integer)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    model: Mapped[str] = mapped_column(String(100))
    mode: Mapped[str] = mapped_column(String(20))  # "full" or "retrieval"
    prompt_version: Mapped[int] = mapped_column(Integer)
    contract_count: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="running")


class EvalResult(Base):
    __tablename__ = "eval_results"

    run_id: Mapped[int] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"), primary_key=True
    )
    clause_type: Mapped[str] = mapped_column(String(60), primary_key=True)
    precision: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    f1: Mapped[float] = mapped_column(Float)
    recall_at_5: Mapped[float | None] = mapped_column(Float)


class ChunkVector(Base):
    __tablename__ = "chunk_vectors"
    __table_args__ = (
        Index(
            "ix_chunk_vectors_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))
