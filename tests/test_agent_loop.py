"""Unit tests for the agent loop.

The LLM client and tool dispatch are mocked so these tests verify the
loop's control flow (plain text, tool call, max-turns cap) without any
real network or DB calls.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.loop import run
from app.infra.llm import ChatResponse, ToolCall

CONVERSATION_ID = "conv-test-1"
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _plain_response(text: str) -> ChatResponse:
    return ChatResponse(content=text, tool_calls=[], provider="openai", model="gpt-4o-mini")


def _tool_response(tool_name: str, args: str, tool_id: str = "tc_1") -> ChatResponse:
    return ChatResponse(
        content=None,
        tool_calls=[ToolCall(id=tool_id, name=tool_name, arguments=args)],
        provider="openai",
        model="gpt-4o-mini",
    )


@pytest.mark.asyncio
async def test_plain_text_response_returned_immediately():
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value=_plain_response("Here is your answer."))
    mock_session = AsyncMock()

    with patch("app.agent.loop.get_llm_client", return_value=mock_llm):
        result = await run(
            messages=[{"role": "user", "content": "Hello"}],
            user_id=USER_ID,
            conversation_id=CONVERSATION_ID,
            session=mock_session,
        )

    assert result == "Here is your answer."
    assert mock_llm.chat.call_count == 1


@pytest.mark.asyncio
async def test_single_tool_call_then_text():
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        side_effect=[
            _tool_response("classify_issue", '{"title": "crash"}'),
            _plain_response("It is a bug."),
        ]
    )
    mock_session = AsyncMock()

    with patch("app.agent.loop.get_llm_client", return_value=mock_llm), \
         patch("app.agent.loop.dispatch", new_callable=AsyncMock, return_value="bug") as mock_dispatch:
        result = await run(
            messages=[{"role": "user", "content": "What type is this?"}],
            user_id=USER_ID,
            conversation_id=CONVERSATION_ID,
            session=mock_session,
        )

    assert result == "It is a bug."
    assert mock_llm.chat.call_count == 2
    mock_dispatch.assert_called_once_with(
        "classify_issue", {"title": "crash"}, USER_ID, CONVERSATION_ID, mock_session
    )


@pytest.mark.asyncio
async def test_max_turns_returns_fallback_message():
    # LLM always returns a tool call → loop hits _MAX_TURNS
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        return_value=_tool_response("classify_issue", '{"title": "x"}')
    )
    mock_session = AsyncMock()

    with patch("app.agent.loop.get_llm_client", return_value=mock_llm), \
         patch("app.agent.loop.dispatch", new_callable=AsyncMock, return_value="bug"), \
         patch("app.agent.loop._MAX_TURNS", 3):
        result = await run(
            messages=[{"role": "user", "content": "Loop forever"}],
            user_id=USER_ID,
            conversation_id=CONVERSATION_ID,
            session=mock_session,
        )

    assert "maximum number of steps" in result
    assert mock_llm.chat.call_count == 3


@pytest.mark.asyncio
async def test_tool_error_does_not_crash_loop():
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        side_effect=[
            _tool_response("search_knowledge_base", '{"query": "auth"}'),
            _plain_response("Sorry, I could not find that."),
        ]
    )
    mock_session = AsyncMock()

    with patch("app.agent.loop.get_llm_client", return_value=mock_llm), \
         patch("app.agent.loop.dispatch", new_callable=AsyncMock, return_value="Tool error (search_knowledge_base): timeout"):
        result = await run(
            messages=[{"role": "user", "content": "Find auth docs"}],
            user_id=USER_ID,
            conversation_id=CONVERSATION_ID,
            session=mock_session,
        )

    # Loop continues and returns the final text reply
    assert result == "Sorry, I could not find that."


@pytest.mark.asyncio
async def test_empty_content_returns_empty_string():
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value=_plain_response(""))
    mock_session = AsyncMock()

    with patch("app.agent.loop.get_llm_client", return_value=mock_llm):
        result = await run(
            messages=[{"role": "user", "content": "Hello"}],
            user_id=USER_ID,
            conversation_id=CONVERSATION_ID,
            session=mock_session,
        )

    assert result == ""
