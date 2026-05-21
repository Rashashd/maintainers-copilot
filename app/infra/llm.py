"""LLM client — OpenAI primary, Anthropic fallback.

Usage:
    from app.infra.llm import get_llm_client
    client = get_llm_client()
    response = await client.chat(messages=[...], tools=[...])

Tools are always passed in OpenAI format. When Anthropic is used as the
fallback, the client converts them to Anthropic's format internally so
the caller never has to know which provider is running.
"""

import json
from dataclasses import dataclass, field
from typing import Any

import anthropic
import openai
import structlog
from langfuse.openai import AsyncOpenAI  # drop-in: auto-captures model, tokens, cost, latency

from app.infra.tracing import get_client, observe

logger = structlog.get_logger()

OPENAI_MODEL = "gpt-4o-mini"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


# ── Response types ────────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON-encoded string


@dataclass
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


# ── Format conversion ─────────────────────────────────────────────────────────

def _to_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Convert OpenAI-format messages (including tool calls) to Anthropic format.

    OpenAI tool call:   {"role": "assistant", "tool_calls": [...]}
    Anthropic equiv:    {"role": "assistant", "content": [{"type": "tool_use", ...}]}

    OpenAI tool result: {"role": "tool", "tool_call_id": "...", "content": "..."}
    Anthropic equiv:    {"role": "user", "content": [{"type": "tool_result", ...}]}
    Consecutive tool results are merged into one user turn.
    """
    result: list[dict] = []
    i = 0
    while i < len(messages):
        m = messages[i]
        role = m["role"]

        if role == "system":
            i += 1
            continue  # handled as top-level system param

        if role == "assistant":
            if m.get("tool_calls"):
                content: list[dict] = []
                if m.get("content"):
                    content.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"]),
                    })
                result.append({"role": "assistant", "content": content})
            else:
                result.append({"role": "assistant", "content": m.get("content") or ""})
            i += 1

        elif role == "tool":
            tool_results: list[dict] = []
            while i < len(messages) and messages[i]["role"] == "tool":
                tm = messages[i]
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tm["tool_call_id"],
                    "content": tm["content"],
                })
                i += 1
            result.append({"role": "user", "content": tool_results})

        else:  # user
            result.append({"role": "user", "content": m.get("content") or ""})
            i += 1

    return result


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    """
    OpenAI tool format  →  Anthropic tool format.

    OpenAI:    {"type": "function", "function": {"name": ..., "parameters": ...}}
    Anthropic: {"name": ..., "input_schema": ...}
    """
    result = []
    for t in tools:
        fn = t.get("function", t)
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


# ── Client ────────────────────────────────────────────────────────────────────

class LLMClient:
    def __init__(self, openai_key: str = "", anthropic_key: str = "") -> None:
        # langfuse.openai.AsyncOpenAI is a drop-in that auto-traces every call
        self._openai = AsyncOpenAI(api_key=openai_key) if openai_key else None
        self._anthropic = anthropic.AsyncAnthropic(api_key=anthropic_key) if anthropic_key else None

        if not self._openai and not self._anthropic:
            raise RuntimeError("At least one LLM API key must be set (openai or anthropic).")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> ChatResponse:
        """Call the LLM. Tries OpenAI first; falls back to Anthropic on failure."""
        if self._openai:
            try:
                return await self._openai_chat(messages, tools, max_tokens)
            except (openai.APIStatusError, openai.APIConnectionError) as exc:
                logger.warning("openai_failed_falling_back", error=str(exc))

        if self._anthropic:
            return await self._anthropic_chat(messages, tools, max_tokens)

        raise RuntimeError("All LLM providers failed.")

    # ── OpenAI ────────────────────────────────────────────────────────────────

    async def _openai_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int,
    ) -> ChatResponse:
        # langfuse.openai integration auto-captures: model, tokens, cost, latency, input, output
        kwargs: dict[str, Any] = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "name": "openai-chat",  # descriptive span name in Langfuse UI
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = await self._openai.chat.completions.create(**kwargs)  # type: ignore[union-attr]
        msg = resp.choices[0].message
        usage = resp.usage

        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments)
            for tc in (msg.tool_calls or [])
        ]
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        logger.info(
            "llm_call",
            provider="openai",
            model=OPENAI_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_calls=[tc.name for tc in tool_calls],
        )
        return ChatResponse(
            content=msg.content,
            tool_calls=tool_calls,
            provider="openai",
            model=OPENAI_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # ── Anthropic ─────────────────────────────────────────────────────────────

    @observe(name="llm.anthropic", as_type="generation")
    async def _anthropic_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int,
    ) -> ChatResponse:
        # Anthropic takes system as a top-level param; tool call/result messages need conversion
        system = ""
        for m in messages:
            if m["role"] == "system":
                system = m["content"]

        converted = _to_anthropic_messages(messages)

        kwargs: dict[str, Any] = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "messages": converted,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _to_anthropic_tools(tools)

        # Set explicit input on the generation span (avoid leaking internal args)
        get_client().update_current_generation(
            model=ANTHROPIC_MODEL,
            input=converted,
        )

        resp = await self._anthropic.messages.create(**kwargs)  # type: ignore[union-attr]

        content_text: str | None = None
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=json.dumps(block.input))
                )

        input_tokens = resp.usage.input_tokens if resp.usage else 0
        output_tokens = resp.usage.output_tokens if resp.usage else 0

        # Push token counts and output to the Langfuse generation span
        get_client().update_current_generation(
            output=content_text,
            usage={"input": input_tokens, "output": output_tokens, "unit": "TOKENS"},
        )
        logger.info(
            "llm_call",
            provider="anthropic",
            model=ANTHROPIC_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_calls=[tc.name for tc in tool_calls],
        )
        return ChatResponse(
            content=content_text,
            tool_calls=tool_calls,
            provider="anthropic",
            model=ANTHROPIC_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


# ── Module-level singleton ────────────────────────────────────────────────────

_client: LLMClient | None = None


def init_llm_client(openai_key: str, anthropic_key: str) -> LLMClient:
    global _client
    _client = LLMClient(openai_key=openai_key, anthropic_key=anthropic_key)
    return _client


def get_llm_client() -> LLMClient:
    if _client is None:
        raise RuntimeError("LLM client not initialised — call init_llm_client() in lifespan first.")
    return _client
