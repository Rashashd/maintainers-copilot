import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Widget


async def get_by_id(session: AsyncSession, widget_id: uuid.UUID) -> Widget | None:
    result = await session.execute(select(Widget).where(Widget.id == widget_id))
    return result.scalar_one_or_none()


async def list_by_owner(session: AsyncSession, owner_id: uuid.UUID) -> list[Widget]:
    result = await session.execute(
        select(Widget)
        .where(Widget.owner_id == owner_id)
        .order_by(Widget.created_at.desc())
    )
    return list(result.scalars().all())


async def list_all(session: AsyncSession, limit: int = 100) -> list[Widget]:
    result = await session.execute(
        select(Widget).order_by(Widget.created_at.asc()).limit(limit)
    )
    return list(result.scalars().all())


async def insert(session: AsyncSession, widget: Widget) -> Widget:
    session.add(widget)
    await session.flush()
    return widget


async def update(session: AsyncSession, widget_id: uuid.UUID, **fields) -> Widget | None:
    widget = await get_by_id(session, widget_id)
    if widget is None:
        return None
    for key, value in fields.items():
        setattr(widget, key, value)
    await session.flush()
    return widget
