import uuid
from datetime import datetime
from typing import List

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    widgets: Mapped[List["Widget"]] = relationship(back_populates="owner")
    memory_entries: Mapped[List["MemoryEntry"]] = relationship(back_populates="user")


class Widget(Base):
    __tablename__ = "widgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed_origins: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, default=list)
    theme: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    greeting: Mapped[str] = mapped_column(Text, default="How can I help you?")
    enabled_tools: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, default=list)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship(back_populates="widgets")


class MemoryEntry(Base):
    """Episodic long-term memory stored in pgvector for semantic retrieval."""

    __tablename__ = "memory_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(Vector(768))  # sentence-transformers dim
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="memory_entries")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # role_change | memory_write | widget_edit | deletion
    target: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {"type": "...", "id": "..."}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InferenceLog(Base):
    """Records every model-server tool call for drift monitoring and debugging."""

    __tablename__ = "inference_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tool: Mapped[str] = mapped_column(String(50), nullable=False)  # classify_issue | extract_entities | summarize_issue
    input_: Mapped[dict] = mapped_column("input", JSONB, nullable=False)
    output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    """RAG corpus: project docs + resolved GitHub issues."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)  # "github_issue" | "docs"
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)  # URL or issue number
    title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list | None] = mapped_column(Vector(768))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
