"""Auth service — fastapi-users wiring.

JWT secret resolved from Vault at request time via get_jwt_signing_key(),
so it is always the value Vault holds at startup (already cached in module _secrets).
"""

import uuid

import structlog
from fastapi import Depends, HTTPException, status
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.infra import vault
from app.repositories import audit as audit_repo

logger = structlog.get_logger()

_JWT_LIFETIME = 86400  # 24 h — one triage session


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    async def on_after_register(self, user: User, request=None) -> None:
        logger.info("user_registered", user_id=str(user.id), email=user.email)

    async def on_after_login(self, user: User, request=None, response=None) -> None:
        logger.info("user_login", user_id=str(user.id), email=user.email)

    async def on_after_update(self, user: User, update_dict: dict, request=None) -> None:
        if "role" in update_dict:
            session = self.user_db.session
            await audit_repo.log(
                session,
                actor_id=user.id,
                action="role_change",
                target={"type": "user", "id": str(user.id), "new_role": update_dict["role"]},
            )
            await session.commit()
            logger.info("role_changed", user_id=str(user.id), new_role=update_dict["role"])


async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
):
    yield UserManager(user_db)


def _get_jwt_strategy() -> JWTStrategy:
    secret = vault.get_jwt_signing_key()
    if not secret:
        raise RuntimeError("JWT signing key not found in Vault — cannot issue tokens.")
    return JWTStrategy(secret=secret, lifetime_seconds=_JWT_LIFETIME)


_bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=_bearer_transport,
    get_strategy=_get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)


async def current_admin(user: User = Depends(current_active_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user
