import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_active_user, get_session
from app.db.models import User
from app.repositories import audit as audit_repo
from app.repositories import memory as memory_repo
from app.schemas.memory import MemoryEntryRead

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/history", response_model=list[MemoryEntryRead])
async def list_history(
    conversation_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> list[MemoryEntryRead]:
    return await memory_repo.list_entries(
        session,
        user_id=user.id,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    entry = await memory_repo.get_by_id(session, entry_id, user.id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory entry not found.")
    await memory_repo.delete_by_id(session, entry_id, user.id)
    await audit_repo.log(
        session,
        actor_id=user.id,
        action="deletion",
        target={"type": "memory_entry", "id": str(entry_id)},
    )
    await session.commit()
