import uuid
from typing import Any

import structlog
from sqlalchemy import delete, desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document

logger = structlog.get_logger()


# ── helpers ───────────────────────────────────────────────────────────────────

def _apply_filters(stmt: Any, filters: dict) -> Any:
    if filters.get("source_repo"):
        stmt = stmt.where(Document.metadata_["source_repo"].astext == filters["source_repo"])
    if filters.get("created_after"):
        stmt = stmt.where(Document.metadata_["created_at"].astext >= filters["created_after"])
    if filters.get("created_before"):
        stmt = stmt.where(Document.metadata_["created_at"].astext <= filters["created_before"])
    return stmt


# ── writes ────────────────────────────────────────────────────────────────────

async def fetch_indexed_source_ids(session: AsyncSession, source_ids: list[str]) -> set[str]:
    if not source_ids:
        return set()
    result = await session.execute(
        select(Document.source_id).where(Document.source_id.in_(source_ids)).distinct()
    )
    return {row[0] for row in result}


async def delete_by_source_ids(session: AsyncSession, source_ids: list[str]) -> None:
    if not source_ids:
        return
    await session.execute(delete(Document).where(Document.source_id.in_(source_ids)))


async def insert_chunks(session: AsyncSession, chunks: list[dict]) -> None:
    for chunk in chunks:
        session.add(Document(
            id=uuid.uuid4(),
            source_type=chunk["source_type"],
            source_id=chunk["source_id"],
            title=chunk.get("title"),
            content=chunk["content"],
            chunk_index=chunk["chunk_index"],
            embedding=chunk["embedding"],
            metadata_=chunk.get("metadata_", {}),
        ))


# ── reads ─────────────────────────────────────────────────────────────────────

async def vector_search(
    session: AsyncSession,
    query_vector: list[float],
    limit: int = 50,
    filters: dict | None = None,
) -> list[Document]:
    stmt = select(Document).where(Document.embedding.is_not(None))
    if filters:
        stmt = _apply_filters(stmt, filters)
    stmt = stmt.order_by(Document.embedding.cosine_distance(query_vector)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def fts_search(
    session: AsyncSession,
    query_text: str,
    limit: int = 50,
    filters: dict | None = None,
) -> list[Document]:
    rank_expr = text(
        "ts_rank(to_tsvector('english', content), plainto_tsquery('english', :q))"
    ).bindparams(q=query_text)
    match_expr = text(
        "to_tsvector('english', content) @@ plainto_tsquery('english', :q)"
    ).bindparams(q=query_text)

    stmt = select(Document).where(match_expr)
    if filters:
        stmt = _apply_filters(stmt, filters)
    stmt = stmt.order_by(desc(rank_expr)).limit(limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def fetch_by_ids(session: AsyncSession, ids: list[uuid.UUID]) -> list[Document]:
    if not ids:
        return []
    result = await session.execute(select(Document).where(Document.id.in_(ids)))
    docs = {d.id: d for d in result.scalars().all()}
    return [docs[doc_id] for doc_id in ids if doc_id in docs]
