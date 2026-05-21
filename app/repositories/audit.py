import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


async def log(
    session: AsyncSession,
    actor_id: uuid.UUID,
    action: str,
    target: dict,
) -> AuditLog:
    entry = AuditLog(
        id=uuid.uuid4(),
        actor_id=actor_id,
        action=action,
        target=target,
    )
    session.add(entry)
    return entry


async def list_by_actor(
    session: AsyncSession,
    actor_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.actor_id == actor_id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_by_action(
    session: AsyncSession,
    action: str,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.action == action)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())
