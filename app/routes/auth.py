from fastapi import APIRouter

from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.auth import auth_backend, fastapi_users

router = APIRouter()

# POST /auth/jwt/login  → returns access_token
# POST /auth/jwt/logout
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

# POST /auth/register
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

# GET  /users/me
# PATCH /users/me
# GET  /users/{id}   (superuser only)
# PATCH /users/{id}  (superuser only)
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
