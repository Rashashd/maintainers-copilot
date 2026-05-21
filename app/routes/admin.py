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
from app.repositories import users as users_repo
from app.schemas.user import UserRead

router = APIRouter(prefix="/admin", tags=["admin"])


class RoleUpdate(BaseModel):
    role: str


class AuditLogRead(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID
    action: str
    target: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class InferenceLogRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: str
    tool: str
    input_: dict
    output: dict
    created_at: datetime

    model_config = {"from_attributes": True}


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
    if action:
        return await audit_repo.list_by_action(  # type: ignore[return-value]
            session, action=action, limit=limit, offset=offset
        )
    result = await session.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())  # type: ignore[return-value]


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
