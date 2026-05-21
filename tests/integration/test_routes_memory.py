"""Tests for GET /memory/history and DELETE /memory/{id}."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_entry(entry_id=None, conv_id="conv-1", role="user", content="hello"):
    entry = MagicMock()
    entry.id = entry_id or uuid.uuid4()
    entry.conversation_id = conv_id
    entry.role = role
    entry.content = content
    entry.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    return entry


@pytest.mark.asyncio
async def test_list_history_returns_entries(client, mock_session):
    entries = [_make_entry(), _make_entry(role="assistant", content="reply")]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = entries
    mock_session.execute = AsyncMock(return_value=result_mock)

    resp = await client.get("/memory/history")

    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_history_empty(client, mock_session):
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)

    resp = await client.get("/memory/history")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_history_requires_auth():

    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.services.auth import current_active_user

    app.dependency_overrides.pop(current_active_user, None)
    with patch("app.services.auth.vault.get_jwt_signing_key", return_value="test-secret"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/memory/history")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_entry_owned(client, mock_session):
    entry_id = uuid.uuid4()
    entry = _make_entry(entry_id=entry_id)

    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = entry
    mock_session.execute = AsyncMock(return_value=scalar_mock)

    resp = await client.delete(f"/memory/{entry_id}")

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_entry_not_found(client, mock_session):
    entry_id = uuid.uuid4()

    scalar_mock = MagicMock()
    scalar_mock.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=scalar_mock)

    resp = await client.delete(f"/memory/{entry_id}")

    assert resp.status_code == 404
