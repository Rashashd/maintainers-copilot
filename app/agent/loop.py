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


@observe(name="agent.loop")
async def run(
    messages: list[dict],
    user_id: uuid.UUID,
    conversation_id: str,
    session: AsyncSession,
) -> str:
    """Run the agent loop and return the final assistant text response.

    Args:
        messages: Conversation history in OpenAI format (no system message).
        user_id: ID of the authenticated user (for write_memory).
        conversation_id: Stable ID for this conversation session.
        session: Active DB session (for RAG + memory tools).
    """
    llm = get_llm_client()
    history: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}] + messages

    for turn in range(_MAX_TURNS):
        response = await llm.chat(history, tools=TOOL_DEFINITIONS, max_tokens=1024)

        if not response.has_tool_calls:
            logger.info("agent_finished", turns=turn + 1)
            return response.content or ""

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
            result = await dispatch(tc.name, args, user_id, conversation_id, session)
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    logger.warning("agent_max_turns_reached", max_turns=_MAX_TURNS)
    return "[Agent reached the maximum number of steps without a final answer.]"
