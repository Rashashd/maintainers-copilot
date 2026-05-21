"""User repository — queries beyond what fastapi-users provides internally.

fastapi-users handles get-by-id, get-by-email, create, update, delete via
SQLAlchemyUserDatabase. This module adds admin-facing queries that aren't
exposed by that adapter.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def list_all(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> list[User]:
    result = await session.execute(
        select(User).order_by(User.email).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def list_by_role(
    session: AsyncSession,
    role: str,
    limit: int = 100,
    offset: int = 0,
) -> list[User]:
    result = await session.execute(
        select(User).where(User.role == role).order_by(User.email).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar_one()
