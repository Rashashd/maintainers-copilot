import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Widget


async def get_by_id(session: AsyncSession, widget_id: uuid.UUID) -> Widget | None:
    result = await session.execute(select(Widget).where(Widget.id == widget_id))
    return result.scalar_one_or_none()


async def update(session: AsyncSession, widget_id: uuid.UUID, **fields) -> Widget | None:
    widget = await get_by_id(session, widget_id)
    if widget is None:
        return None
    for key, value in fields.items():
        setattr(widget, key, value)
    await session.flush()
    return widget
