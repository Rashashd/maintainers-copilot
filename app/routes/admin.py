import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_admin, get_session
from app.db.models import AuditLog, InferenceLog, User
from app.repositories import audit as audit_repo
from app.repositories import inference as inference_repo
from app.repositories import memory as memory_repo
from app.repositories import users as users_repo
from app.repositories import widget as widget_repo
from app.schemas.user import UserRead
from app.schemas.widget import WidgetRead

router = APIRouter(prefix="/admin", tags=["admin"])


class RoleUpdate(BaseModel):
    role: str


class AuditLogRead(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID
    actor_email: str | None = None
    action: str
    target: dict
    created_at: datetime


class InferenceLogRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: str
    tool: str
    input_: dict
    output: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryEntryAdmin(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime


@router.get("/widgets", response_model=list[WidgetRead])
async def list_widgets(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(current_admin),
) -> list[WidgetRead]:
    """Return all widgets owned by the current admin."""
    return await widget_repo.list_by_owner(session, admin.id)  # type: ignore[return-value]


@router.get("/users", response_model=list[UserRead])
async def list_users(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(current_admin),
) -> list[UserRead]:
    return await users_repo.list_all(session, limit=limit, offset=offset)  # type: ignore[return-value]


@router.patch("/users/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: uuid.UUID,
    body: RoleUpdate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(current_admin),
) -> UserRead:
    if body.role not in ("user", "admin"):
        raise HTTPException(status_code=422, detail="role must be 'user' or 'admin'")
    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if body.role == "user" and user.role == "admin":
        admins = await users_repo.list_by_role(session, "admin")
        if len(admins) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot demote the last admin. Promote another user first.",
            )
    user.role = body.role
    await audit_repo.log(
        session,
        actor_id=admin.id,
        action="role_change",
        target={"type": "user", "id": str(user_id), "new_role": body.role},
    )
    await session.commit()
    await session.refresh(user)
    return user  # type: ignore[return-value]


@router.get("/audit", response_model=list[AuditLogRead])
async def list_audit_logs(
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(current_admin),
) -> list[AuditLogRead]:
    stmt = (
        select(AuditLog, User.email)
        .outerjoin(User, AuditLog.actor_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = await session.execute(stmt)
    return [
        AuditLogRead(
            id=log.id,
            actor_id=log.actor_id,
            actor_email=email,
            action=log.action,
            target=log.target,
            created_at=log.created_at,
        )
        for log, email in rows.all()
    ]


@router.get("/memory", response_model=list[MemoryEntryAdmin])
async def list_all_memory(
    user_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(current_admin),
) -> list[MemoryEntryAdmin]:
    rows = await memory_repo.list_all_entries(session, user_id=user_id, limit=limit, offset=offset)
    return [
        MemoryEntryAdmin(
            id=entry.id,
            user_id=entry.user_id,
            user_email=email,
            conversation_id=entry.conversation_id,
            role=entry.role,
            content=entry.content,
            created_at=entry.created_at,
        )
        for entry, email in rows
    ]


@router.get("/inference", response_model=list[InferenceLogRead])
async def list_inference_logs(
    tool: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(current_admin),
) -> list[InferenceLogRead]:
    if tool:
        return await inference_repo.list_by_tool(  # type: ignore[return-value]
            session, tool=tool, limit=limit, offset=offset
        )
    result = await session.execute(
        select(InferenceLog).order_by(InferenceLog.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())  # type: ignore[return-value]
