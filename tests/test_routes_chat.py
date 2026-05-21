"""Integration-style tests for POST /chat.

Agent loop, memory service, and DB session are all mocked so these tests
verify route wiring, auth enforcement, and response shape.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_chat_returns_reply(client):
    with patch("app.routes.chat.agent_loop.run", new_callable=AsyncMock, return_value="Here is my answer."), \
         patch("app.routes.chat.memory_service.load_history", new_callable=AsyncMock, return_value=[]), \
         patch("app.routes.chat.memory_service.save_history", new_callable=AsyncMock), \
         patch("app.routes.chat.memory_service.persist_turns", new_callable=AsyncMock):
        resp = await client.post("/chat", json={"message": "Hello"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Here is my answer."
    assert "conversation_id" in body


@pytest.mark.asyncio
async def test_chat_preserves_supplied_conversation_id(client):
    cid = "my-session-123"
    with patch("app.routes.chat.agent_loop.run", new_callable=AsyncMock, return_value="reply"), \
         patch("app.routes.chat.memory_service.load_history", new_callable=AsyncMock, return_value=[]), \
         patch("app.routes.chat.memory_service.save_history", new_callable=AsyncMock), \
         patch("app.routes.chat.memory_service.persist_turns", new_callable=AsyncMock):
        resp = await client.post("/chat", json={"message": "Hi", "conversation_id": cid})

    assert resp.json()["conversation_id"] == cid


@pytest.mark.asyncio
async def test_chat_passes_history_to_loop(client):
    stored = [{"role": "user", "content": "Previous message"}]
    with patch("app.routes.chat.agent_loop.run", new_callable=AsyncMock, return_value="ok") as mock_run, \
         patch("app.routes.chat.memory_service.load_history", new_callable=AsyncMock, return_value=stored), \
         patch("app.routes.chat.memory_service.save_history", new_callable=AsyncMock), \
         patch("app.routes.chat.memory_service.persist_turns", new_callable=AsyncMock):
        await client.post("/chat", json={"message": "New message"})

    # mock stores a reference to the list, which gets mutated after run() returns.
    # Check presence of both messages by content rather than position.
    messages_arg = mock_run.call_args[1]["messages"]
    contents = [m["content"] for m in messages_arg]
    assert "Previous message" in contents
    assert "New message" in contents


@pytest.mark.asyncio
async def test_chat_empty_message_rejected(client):
    resp = await client.post("/chat", json={"message": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_requires_auth():
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.services.auth import current_active_user

    app.dependency_overrides.pop(current_active_user, None)
    # Vault is not running in tests; provide a dummy secret so the strategy
    # can be instantiated and return 401 rather than 500.
    with patch("app.services.auth.vault.get_jwt_signing_key", return_value="test-secret"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/chat", json={"message": "Hello"})

    assert resp.status_code == 401
