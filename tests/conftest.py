"""Shared test fixtures.

Strategy: no real DB/Redis/LLM in unit tests.
- DB session → AsyncMock (SQLAlchemy calls are mocked per test)
- current_active_user → hard-coded test User
- Infrastructure singletons (LLM, Redis) are patched per test where needed
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import User
from app.db.session import get_session
from app.main import app
from app.services.auth import current_active_user

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_USER = User(
    id=TEST_USER_ID,
    email="test@example.com",
    hashed_password="hashed",
    role="user",
    is_active=True,
    is_superuser=False,
    is_verified=True,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
async def client(mock_session: AsyncMock) -> AsyncClient:
    async def _override_session():
        yield mock_session

    app.dependency_overrides[current_active_user] = lambda: TEST_USER
    app.dependency_overrides[get_session] = _override_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
