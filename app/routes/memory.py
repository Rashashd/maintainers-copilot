import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEntry, User
from app.db.session import get_session
from app.services.auth import current_active_user

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryEntryRead(BaseModel):
    id: uuid.UUID
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/history", response_model=list[MemoryEntryRead])
async def list_history(
    conversation_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> list[MemoryEntryRead]:
    stmt = (
        select(MemoryEntry)
        .where(MemoryEntry.user_id == user.id)
        .order_by(MemoryEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if conversation_id:
        stmt = stmt.where(MemoryEntry.conversation_id == conversation_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.execute(
        select(MemoryEntry).where(
            MemoryEntry.id == entry_id, MemoryEntry.user_id == user.id
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory entry not found.")
    await session.execute(
        delete(MemoryEntry).where(
            MemoryEntry.id == entry_id, MemoryEntry.user_id == user.id
        )
    )
    await session.commit()
