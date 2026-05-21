"""Unit tests for the LLM client — both providers and the fallback.

No real API calls are made; OpenAI and Anthropic SDK clients are mocked.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infra.llm import (
    ChatResponse,
    LLMClient,
    ToolCall,
    _to_anthropic_messages,
    _to_anthropic_tools,
)


# ── _to_anthropic_messages ────────────────────────────────────────────────────

def test_system_message_stripped():
    msgs = [
        {"role": "system", "content": "You are an assistant."},
        {"role": "user", "content": "Hello"},
    ]
    result = _to_anthropic_messages(msgs)
    assert len(result) == 1
    assert result[0] == {"role": "user", "content": "Hello"}


def test_plain_user_and_assistant():
    msgs = [
        {"role": "user", "content": "What is a bug?"},
        {"role": "assistant", "content": "A bug is an error."},
    ]
    result = _to_anthropic_messages(msgs)
    assert result[0] == {"role": "user", "content": "What is a bug?"}
    assert result[1] == {"role": "assistant", "content": "A bug is an error."}


def test_assistant_with_tool_calls():
    msgs = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "tc_1",
                    "type": "function",
                    "function": {
                        "name": "classify_issue",
                        "arguments": '{"title": "crash"}',
                    },
                }
            ],
        }
    ]
    result = _to_anthropic_messages(msgs)
    content = result[0]["content"]
    assert content[0]["type"] == "tool_use"
    assert content[0]["id"] == "tc_1"
    assert content[0]["name"] == "classify_issue"
    assert content[0]["input"] == {"title": "crash"}


def test_assistant_text_plus_tool_call():
    msgs = [
        {
            "role": "assistant",
            "content": "Let me check.",
            "tool_calls": [
                {
                    "id": "tc_2",
                    "type": "function",
                    "function": {
                        "name": "search_knowledge_base",
                        "arguments": '{"query": "login"}',
                    },
                }
            ],
        }
    ]
    result = _to_anthropic_messages(msgs)
    content = result[0]["content"]
    assert content[0] == {"type": "text", "text": "Let me check."}
    assert content[1]["type"] == "tool_use"


def test_consecutive_tool_results_merged_into_one_user_turn():
    msgs = [
        {"role": "tool", "tool_call_id": "tc_1", "content": "Result A"},
        {"role": "tool", "tool_call_id": "tc_2", "content": "Result B"},
    ]
    result = _to_anthropic_messages(msgs)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert len(result[0]["content"]) == 2
    assert result[0]["content"][0]["tool_use_id"] == "tc_1"
    assert result[0]["content"][1]["tool_use_id"] == "tc_2"


def test_full_conversation_round():
    msgs = [
        {"role": "system", "content": "System."},
        {"role": "user", "content": "Classify this."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "tc_1",
                    "type": "function",
                    "function": {
                        "name": "classify_issue",
                        "arguments": '{"title": "crash"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "tc_1", "content": "bug"},
        {"role": "assistant", "content": "It is a bug."},
    ]
    result = _to_anthropic_messages(msgs)
    # system stripped → user, assistant(tool_use), user(tool_result), assistant
    assert len(result) == 4
    assert result[2]["role"] == "user"
    assert result[2]["content"][0]["type"] == "tool_result"
    assert result[3]["content"] == "It is a bug."


# ── _to_anthropic_tools ───────────────────────────────────────────────────────

def test_tool_format_conversion():
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "classify_issue",
                "description": "Classify a GitHub issue.",
                "parameters": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                    "required": ["title"],
                },
            },
        }
    ]
    result = _to_anthropic_tools(openai_tools)
    assert result[0]["name"] == "classify_issue"
    assert result[0]["description"] == "Classify a GitHub issue."
    assert "title" in result[0]["input_schema"]["properties"]


def test_tool_missing_description_defaults_empty():
    tools = [{"type": "function", "function": {"name": "t", "parameters": {"type": "object", "properties": {}}}}]
    assert _to_anthropic_tools(tools)[0]["description"] == ""


# ── OpenAI chat path ──────────────────────────────────────────────────────────

def _make_openai_response(content: str | None, tool_calls=None):
    """Build a minimal mock of openai ChatCompletion response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 5
    return resp


@pytest.mark.asyncio
async def test_openai_plain_text_response():
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(
        return_value=_make_openai_response("Hello from OpenAI")
    )

    with patch("app.infra.llm.AsyncOpenAI", return_value=mock_openai):
        client = LLMClient(openai_key="sk-test")
        client._openai = mock_openai
        response = await client.chat([{"role": "user", "content": "Hi"}])

    assert response.content == "Hello from OpenAI"
    assert response.provider == "openai"
    assert not response.has_tool_calls


@pytest.mark.asyncio
async def test_openai_tool_call_response():
    tc = MagicMock()
    tc.id = "tc_1"
    tc.function.name = "classify_issue"
    tc.function.arguments = '{"title": "crash"}'

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(
        return_value=_make_openai_response(None, tool_calls=[tc])
    )

    with patch("app.infra.llm.AsyncOpenAI", return_value=mock_openai):
        client = LLMClient(openai_key="sk-test")
        client._openai = mock_openai
        response = await client.chat([{"role": "user", "content": "Classify"}], tools=[])

    assert response.has_tool_calls
    assert response.tool_calls[0].name == "classify_issue"
    assert response.tool_calls[0].id == "tc_1"


# ── Anthropic chat path ───────────────────────────────────────────────────────

def _make_anthropic_response(text: str | None = None, tool_uses=None):
    blocks = []
    if text:
        b = MagicMock()
        b.type = "text"
        b.text = text
        blocks.append(b)
    for tu in (tool_uses or []):
        b = MagicMock()
        b.type = "tool_use"
        b.id = tu["id"]
        b.name = tu["name"]
        b.input = tu["input"]
        blocks.append(b)
    resp = MagicMock()
    resp.content = blocks
    resp.usage.input_tokens = 8
    resp.usage.output_tokens = 4
    return resp


@pytest.mark.asyncio
async def test_anthropic_plain_text_response():
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(text="Hello from Anthropic")
    )

    with patch("app.infra.llm.get_client") as mock_get_client:
        mock_get_client.return_value.update_current_generation = MagicMock()
        client = LLMClient(anthropic_key="sk-ant-test")
        client._openai = None
        client._anthropic = mock_anthropic
        response = await client.chat([{"role": "user", "content": "Hi"}])

    assert response.content == "Hello from Anthropic"
    assert response.provider == "anthropic"
    assert not response.has_tool_calls


@pytest.mark.asyncio
async def test_anthropic_tool_call_response():
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(
            tool_uses=[{"id": "tu_1", "name": "search_knowledge_base", "input": {"query": "auth"}}]
        )
    )

    with patch("app.infra.llm.get_client") as mock_get_client:
        mock_get_client.return_value.update_current_generation = MagicMock()
        client = LLMClient(anthropic_key="sk-ant-test")
        client._openai = None
        client._anthropic = mock_anthropic
        response = await client.chat([{"role": "user", "content": "Search"}], tools=[])

    assert response.has_tool_calls
    assert response.tool_calls[0].name == "search_knowledge_base"
    assert response.tool_calls[0].arguments == '{"query": "auth"}'


# ── Fallback: OpenAI fails → Anthropic used ──────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_to_anthropic_on_openai_error():
    import openai

    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(
        side_effect=openai.APIConnectionError(request=MagicMock())
    )
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(text="Fallback response")
    )

    with patch("app.infra.llm.get_client") as mock_get_client:
        mock_get_client.return_value.update_current_generation = MagicMock()
        client = LLMClient(openai_key="sk-test", anthropic_key="sk-ant-test")
        client._openai = mock_openai
        client._anthropic = mock_anthropic
        response = await client.chat([{"role": "user", "content": "Hi"}])

    assert response.provider == "anthropic"
    assert response.content == "Fallback response"
