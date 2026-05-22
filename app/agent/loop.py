"""Agent loop — single LLM that picks tools, not a multi-agent framework.

The loop:
  1. Prepend system prompt to conversation history.
  2. Call LLM with tool definitions.
  3. If the response contains tool calls, execute each, append results, repeat.
  4. If the response is plain text, return it.
  5. Stop after max_turns to prevent runaway loops.
"""

import json
import uuid
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.registry import TOOL_DEFINITIONS, dispatch
from app.infra.llm import get_llm_client
from app.infra.tracing import observe

logger = structlog.get_logger()

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.txt").read_text()
_MAX_TURNS = 10

_TOOL_STATUS: dict[str, str] = {
    "classify_issue": "Classifying issue…",
    "extract_entities": "Extracting entities…",
    "summarize_issue": "Summarizing…",
    "search_knowledge_base": "Searching knowledge base…",
    "write_memory": "Saving to memory…",
}


@observe(name="agent.loop")
async def run(
    messages: list[dict],
    user_id: uuid.UUID | None,
    conversation_id: str,
    session: AsyncSession,
    tool_definitions: list[dict] | None = None,
) -> tuple[str, list[str]]:
    """Run the agent loop and return (final_text, tools_used).

    Args:
        messages: Conversation history in OpenAI format (no system message).
        user_id: Authenticated user ID, or None for anonymous widget sessions.
        conversation_id: Stable ID for this conversation session.
        session: Active DB session (for RAG + memory tools).
        tool_definitions: Override the default tool list (used by widget chat).
    """
    llm = get_llm_client()
    history: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}] + messages
    tools = tool_definitions if tool_definitions is not None else TOOL_DEFINITIONS
    tools_used: list[str] = []

    for turn in range(_MAX_TURNS):
        response = await llm.chat(history, tools=tools, max_tokens=1024)

        if not response.has_tool_calls:
            logger.info("agent_finished", turns=turn + 1, tools_used=tools_used)
            return response.content or "", tools_used

        # Append the assistant turn (with tool calls) to history
        history.append({
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in response.tool_calls
            ],
        })

        # Execute each tool and append results
        for tc in response.tool_calls:
            args = json.loads(tc.arguments)
            logger.info("agent_tool_call", tool=tc.name, turn=turn + 1)
            tools_used.append(tc.name)
            result = await dispatch(tc.name, args, user_id, conversation_id, session)
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    logger.warning("agent_max_turns_reached", max_turns=_MAX_TURNS)
    return "[Agent reached the maximum number of steps without a final answer.]", tools_used


@observe(name="agent.loop.stream")
async def stream(
    messages: list[dict],
    user_id: uuid.UUID | None,
    conversation_id: str,
    session,
    tool_definitions: list[dict] | None = None,
):
    """Streaming agent loop. Yields SSE-ready event dicts:
      {type: "status", text: "..."}   — tool being called
      {type: "token",  text: "..."}   — answer token
      {type: "done"}                  — stream complete
    """
    llm = get_llm_client()
    history: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}] + messages
    tools = tool_definitions if tool_definitions is not None else TOOL_DEFINITIONS

    for turn in range(_MAX_TURNS):
        tool_calls_this_turn: list = []
        content_this_turn = ""

        async for ev in llm.chat_stream(history, tools=tools, max_tokens=1024):
            if ev["type"] == "token":
                content_this_turn += ev["text"]
                yield ev
            elif ev["type"] == "tool_calls":
                tool_calls_this_turn = ev["calls"]
            # "done" from LLM is ignored here; we emit our own done below

        if not tool_calls_this_turn:
            logger.info("agent_stream_finished", turns=turn + 1)
            yield {"type": "done"}
            return

        # Append assistant turn with tool calls to history
        history.append({
            "role": "assistant",
            "content": content_this_turn or None,
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in tool_calls_this_turn
            ],
        })

        for tc in tool_calls_this_turn:
            yield {"type": "status", "text": _TOOL_STATUS.get(tc.name, f"Using {tc.name}…")}
            args = json.loads(tc.arguments)
            logger.info("agent_tool_call", tool=tc.name, turn=turn + 1)
            result = await dispatch(tc.name, args, user_id, conversation_id, session)
            history.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    logger.warning("agent_stream_max_turns_reached", max_turns=_MAX_TURNS)
    yield {"type": "done"}
