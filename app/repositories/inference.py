import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InferenceLog


async def log(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: str,
    tool: str,
    input_: dict,
    output: dict,
) -> InferenceLog:
    entry = InferenceLog(
        id=uuid.uuid4(),
        user_id=user_id,
        conversation_id=conversation_id,
        tool=tool,
        input_=input_,
        output=output,
    )
    session.add(entry)
    return entry


async def list_by_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    tool: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[InferenceLog]:
    stmt = (
        select(InferenceLog)
        .where(InferenceLog.user_id == user_id)
        .order_by(InferenceLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if tool:
        stmt = stmt.where(InferenceLog.tool == tool)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_by_tool(
    session: AsyncSession,
    tool: str,
    limit: int = 100,
    offset: int = 0,
) -> list[InferenceLog]:
    result = await session.execute(
        select(InferenceLog)
        .where(InferenceLog.tool == tool)
        .order_by(InferenceLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())
