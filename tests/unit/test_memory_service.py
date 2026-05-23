"""Unit tests for the memory service (Redis + pgvector persistence)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import memory as memory_service

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
CONV_ID = "conv-test-1"


@pytest.mark.asyncio
async def test_load_history_returns_list_from_redis():
    stored = [{"role": "user", "content": "Hello"}]
    with patch("app.services.memory.redis.get_json", new_callable=AsyncMock, return_value=stored):
        result = await memory_service.load_history(USER_ID, CONV_ID)
    assert result == stored


@pytest.mark.asyncio
async def test_load_history_returns_empty_list_when_key_missing():
    with patch("app.services.memory.redis.get_json", new_callable=AsyncMock, return_value=None):
        result = await memory_service.load_history(USER_ID, CONV_ID)
    assert result == []


@pytest.mark.asyncio
async def test_save_history_calls_set_json_with_correct_key_and_ttl():
    messages = [{"role": "user", "content": "Hi"}]
    with patch("app.services.memory.redis.set_json", new_callable=AsyncMock) as mock_set:
        await memory_service.save_history(USER_ID, CONV_ID, messages)

    expected_key = f"conv:{USER_ID}:{CONV_ID}"
    mock_set.assert_called_once_with(expected_key, messages, ttl=7200)


@pytest.mark.asyncio
async def test_persist_turns_creates_two_memory_entries():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    fake_vectors = [[0.1] * 768, [0.2] * 768]

    _embed = patch(
        "app.services.memory.embedder.embed_texts",
        new_callable=AsyncMock,
        return_value=fake_vectors,
    )
    with _embed:
        await memory_service.persist_turns(
            USER_ID, CONV_ID, "user message", "assistant reply", mock_session
        )

    assert mock_session.add.call_count == 2
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_persist_turns_handles_empty_embeddings_gracefully():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with patch("app.services.memory.embedder.embed_texts", new_callable=AsyncMock, return_value=[]):
        await memory_service.persist_turns(
            USER_ID, CONV_ID, "user message", "assistant reply", mock_session
        )

    # Should still add two entries, just with embedding=None
    assert mock_session.add.call_count == 2
