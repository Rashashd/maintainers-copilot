import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEntry, User


async def insert(session: AsyncSession, entries: list[MemoryEntry]) -> None:
    for entry in entries:
        session.add(entry)


async def search_similar(
    session: AsyncSession,
    user_id: uuid.UUID,
    embedding: list[float],
    current_conversation_id: str,
    limit: int = 5,
) -> list[MemoryEntry]:
    """Return past entries most similar to `embedding`, excluding the current conversation."""
    result = await session.execute(
        select(MemoryEntry)
        .where(
            MemoryEntry.user_id == user_id,
            MemoryEntry.conversation_id != current_conversation_id,
            MemoryEntry.embedding.isnot(None),
        )
        .order_by(MemoryEntry.embedding.cosine_distance(embedding))
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_entries(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MemoryEntry]:
    stmt = (
        select(MemoryEntry)
        .where(MemoryEntry.user_id == user_id)
        .order_by(MemoryEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if conversation_id:
        stmt = stmt.where(MemoryEntry.conversation_id == conversation_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession,
    entry_id: uuid.UUID,
    user_id: uuid.UUID,
) -> MemoryEntry | None:
    result = await session.execute(
        select(MemoryEntry).where(
            MemoryEntry.id == entry_id, MemoryEntry.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def delete_by_id(
    session: AsyncSession,
    entry_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await session.execute(
        delete(MemoryEntry).where(
            MemoryEntry.id == entry_id, MemoryEntry.user_id == user_id
        )
    )


async def list_all_entries(
    session: AsyncSession,
    user_id: uuid.UUID | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[tuple[MemoryEntry, str]]:
    """Return all memory entries joined with user email. Admin use only."""
    stmt = (
        select(MemoryEntry, User.email)
        .join(User, MemoryEntry.user_id == User.id)
        .order_by(MemoryEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if user_id is not None:
        stmt = stmt.where(MemoryEntry.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.all())
