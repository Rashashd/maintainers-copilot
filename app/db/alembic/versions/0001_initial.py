"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── pgvector extension ────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── user (managed by fastapi-users) ──────────────────────────────────────
    op.create_table(
        "user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    # ── widgets ───────────────────────────────────────────────────────────────
    op.create_table(
        "widgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("allowed_origins", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("theme", postgresql.JSONB(), nullable=False),
        sa.Column("greeting", sa.Text(), nullable=True),
        sa.Column("enabled_tools", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── memory_entries ────────────────────────────────────────────────────────
    op.create_table(
        "memory_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("conversation_id", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),  # rendered as vector(768) below
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # alter embedding column to proper vector type after extension is enabled
    op.execute("ALTER TABLE memory_entries ALTER COLUMN embedding TYPE vector(768) USING NULL")
    op.execute(
        "CREATE INDEX ix_memory_entries_embedding_hnsw "
        "ON memory_entries USING hnsw (embedding vector_cosine_ops)"
    )

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── documents (RAG corpus) ────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.String(512), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", sa.Text(), nullable=True),  # rendered as vector(768) below
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("ALTER TABLE documents ALTER COLUMN embedding TYPE vector(768) USING NULL")
    # HNSW index for fast cosine-similarity ANN search
    op.execute(
        "CREATE INDEX ix_documents_embedding_hnsw "
        "ON documents USING hnsw (embedding vector_cosine_ops)"
    )
    # GIN index for fast full-text search (BM25 hybrid)
    op.execute(
        "CREATE INDEX ix_documents_content_fts "
        "ON documents USING gin (to_tsvector('english', content))"
    )
    op.create_index("ix_documents_source_id", "documents", ["source_id"])


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("audit_logs")
    op.drop_table("memory_entries")
    op.drop_table("widgets")
    op.drop_table("user")
    op.execute("DROP EXTENSION IF EXISTS vector")
