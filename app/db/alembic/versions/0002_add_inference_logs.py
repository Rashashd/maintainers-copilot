"""add inference_logs table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inference_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("conversation_id", sa.String(255), nullable=False),
        sa.Column("tool", sa.String(50), nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=False),
        sa.Column("output", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_inference_logs_user_id", "inference_logs", ["user_id"])
    op.create_index("ix_inference_logs_tool", "inference_logs", ["tool"])


def downgrade() -> None:
    op.drop_table("inference_logs")
