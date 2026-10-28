"""Initial schema.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("overview", sa.Text),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("status_detail", sa.Text),
        sa.Column("risk_score", sa.Integer),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "contract_id",
            sa.Integer,
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("start_char", sa.Integer, nullable=False),
        sa.Column("end_char", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
    )
    op.create_table(
        "clause_extractions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "contract_id",
            sa.Integer,
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("clause_type", sa.String(60), nullable=False),
        sa.Column("found", sa.Boolean, nullable=False),
        sa.Column("quote", sa.Text),
        sa.Column("start_char", sa.Integer),
        sa.Column("end_char", sa.Integer),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("risk_level", sa.String(10)),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.Integer, nullable=False),
    )
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("prompt_version", sa.Integer, nullable=False),
        sa.Column("contract_count", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Float, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )
    op.create_table(
        "eval_results",
        sa.Column(
            "run_id",
            sa.Integer,
            sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("clause_type", sa.String(60), primary_key=True),
        sa.Column("precision", sa.Float, nullable=False),
        sa.Column("recall", sa.Float, nullable=False),
        sa.Column("f1", sa.Float, nullable=False),
        sa.Column("recall_at_5", sa.Float),
    )
    op.create_table(
        "chunk_vectors",
        sa.Column(
            "chunk_id",
            sa.Integer,
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "contract_id",
            sa.Integer,
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("embedding", Vector(1536), nullable=False),
    )
    op.execute(
        "CREATE INDEX ix_chunk_vectors_embedding ON chunk_vectors "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    for table in (
        "chunk_vectors",
        "eval_results",
        "eval_runs",
        "clause_extractions",
        "chunks",
        "contracts",
    ):
        op.drop_table(table)
