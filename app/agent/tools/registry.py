"""Tool definitions (OpenAI format) and dispatch table for the agent loop."""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import classify, ner, rag, summarize, write_memory
from app.repositories import inference as inference_repo
from app.schemas.errors import ToolFailure

# Tools whose results are logged to inference_logs
_INFERENCE_TOOLS = {"classify_issue", "extract_entities", "summarize_issue"}

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "classify_issue",
            "description": "Classify a GitHub issue as bug, feature, docs, or question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Issue title."},
                    "body": {"type": "string", "description": "Issue body text (optional)."},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_entities",
            "description": (
                "Extract technical entities (function names, file paths,"
                " error codes) from issue text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Issue title and body combined."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_issue",
            "description": "Summarize a long issue or comment thread into concise bullet points.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Full issue text including comments.",
                    },
                    "max_sentences": {
                        "type": "integer",
                        "description": "Max sentences in summary (default 3).",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search resolved issues and project documentation to answer questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The question to answer."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_memory",
            "description": (
                "Save an important fact or piece of context to long-term memory"
                " for future conversations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The information to remember."},
                },
                "required": ["content"],
            },
        },
    },
]


async def dispatch(
    name: str,
    args: dict,
    user_id: uuid.UUID,
    conversation_id: str,
    session: AsyncSession,
) -> str:
    """Execute a tool by name and return the result as a string."""
    try:
        if name == "classify_issue":
            result = await classify.run(args)
        elif name == "extract_entities":
            result = await ner.run(args)
        elif name == "summarize_issue":
            result = await summarize.run(args)
        elif name == "search_knowledge_base":
            return await rag.run(args, session)
        elif name == "write_memory":
            return await write_memory.run(args, user_id, conversation_id, session)
        else:
            return f"Unknown tool: {name}"

        if name in _INFERENCE_TOOLS:
            try:
                output = json.loads(result)
            except (ValueError, TypeError):
                output = {"result": result}
            await inference_repo.log(
                session,
                user_id=user_id,
                conversation_id=conversation_id,
                tool=name,
                input_=args,
                output=output,
            )
            await session.commit()

        return result

    except ToolFailure as exc:
        return f"Tool error ({exc.tool}): {exc.reason}"
    except Exception as exc:
        return f"Tool error ({name}): {exc}"
