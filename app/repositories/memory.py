import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEntry


async def insert(session: AsyncSession, entries: list[MemoryEntry]) -> None:
    for entry in entries:
        session.add(entry)


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
