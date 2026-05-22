import json
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import loop as agent_loop
from app.agent.tools.registry import TOOL_DEFINITIONS
from app.core.deps import current_admin, get_session
from app.db.models import User, Widget
from app.infra import redis
from app.repositories import audit as audit_repo
from app.repositories import widget as widget_repo
from app.schemas.widget import (
    WidgetChatRequest,
    WidgetChatResponse,
    WidgetCreate,
    WidgetRead,
    WidgetUpdate,
)

logger = structlog.get_logger()

_WIDGET_TTL = 1800  # 30 min — anonymous visitor sessions expire quickly

router = APIRouter(prefix="/widget", tags=["widget"])


@router.post("/config", response_model=WidgetRead, status_code=201)
async def create_widget(
    body: WidgetCreate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(current_admin),
) -> WidgetRead:
    """Admin only — create a new widget."""
    widget = Widget(
        name=body.name,
        allowed_origins=body.allowed_origins,
        theme=body.theme,
        greeting=body.greeting,
        enabled_tools=body.enabled_tools,
        owner_id=admin.id,
    )
    await widget_repo.insert(session, widget)
    await audit_repo.log(
        session,
        actor_id=admin.id,
        action="widget_create",
        target={"type": "widget", "id": str(widget.id), "name": widget.name},
    )
    await session.commit()
    await session.refresh(widget)
    return WidgetRead.model_validate(widget)


@router.post("/{widget_id}/chat", response_model=WidgetChatResponse)
async def widget_chat(
    widget_id: uuid.UUID,
    body: WidgetChatRequest,
    session: AsyncSession = Depends(get_session),
) -> WidgetChatResponse:
    """Public — anonymous chat for embedded widget visitors. No JWT required."""
    widget = await widget_repo.get_by_id(session, widget_id)
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found.")

    session_id = body.session_id or str(uuid.uuid4())
    redis_key = f"widget:{widget_id}:{session_id}"

    history = await redis.get_json(redis_key) or []
    history.append({"role": "user", "content": body.message})

    # Only tools listed in widget.enabled_tools; write_memory excluded (no user account)
    enabled = set(widget.enabled_tools or [])
    tools = [t for t in TOOL_DEFINITIONS if t["function"]["name"] in enabled]

    logger.info("widget_chat", widget_id=str(widget_id), session_id=session_id)
    reply, _ = await agent_loop.run(
        messages=history,
        user_id=None,
        conversation_id=session_id,
        session=session,
        tool_definitions=tools,
    )

    history.append({"role": "assistant", "content": reply})
    await redis.set_json(redis_key, history, ttl=_WIDGET_TTL)

    return WidgetChatResponse(reply=reply, session_id=session_id)


@router.post("/{widget_id}/chat/stream")
async def widget_chat_stream(
    widget_id: uuid.UUID,
    body: WidgetChatRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Public — streaming SSE version of widget chat. Emits status + token + done events."""
    widget = await widget_repo.get_by_id(session, widget_id)
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found.")

    session_id = body.session_id or str(uuid.uuid4())
    redis_key = f"widget:{widget_id}:{session_id}"

    history = await redis.get_json(redis_key) or []
    history.append({"role": "user", "content": body.message})

    enabled = set(widget.enabled_tools or [])
    tools = [t for t in TOOL_DEFINITIONS if t["function"]["name"] in enabled]

    logger.info("widget_chat_stream", widget_id=str(widget_id), session_id=session_id)

    async def generate():
        full_reply = ""
        async for event in agent_loop.stream(
            messages=history,
            user_id=None,
            conversation_id=session_id,
            session=session,
            tool_definitions=tools,
        ):
            if event["type"] == "token":
                full_reply += event["text"]
                yield f"data: {json.dumps(event)}\n\n"
            elif event["type"] == "done":
                history.append({"role": "assistant", "content": full_reply})
                await redis.set_json(redis_key, history, ttl=_WIDGET_TTL)
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/config/{widget_id}", response_model=WidgetRead)
async def get_widget_config(
    widget_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> WidgetRead:
    """Public — returns widget config (JSON)."""
    widget = await widget_repo.get_by_id(session, widget_id)
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found.")
    return WidgetRead.model_validate(widget)


@router.get("/embed/{widget_id}", include_in_schema=False)
async def embed_widget(
    widget_id: uuid.UUID,
    response: Response,
    widget_host: str = "http://localhost:3000",
    api: str = "http://localhost:8000",
    slot: int = 0,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Public — HTML shell that hosts the React app inside the iframe.

    CSP frame-ancestors is set here (on the document the browser loads inside
    the outer iframe) so the browser enforces the allowed-origins list.
    An inner iframe loads the React app from widget_host with query params —
    this works with both the Vite dev server (index.html) and the nginx-served
    production build (dist/index.html -> widget.js).
    """
    widget = await widget_repo.get_by_id(session, widget_id)
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found.")

    origins = " ".join(widget.allowed_origins) if widget.allowed_origins else "'none'"
    inner_src = (
        f"{widget_host}/"
        f"?widget_id={widget_id}"
        f"&api={api}"
        f"&slot={slot}"
    )
    html = (
        "<!doctype html><html><head>"
        "<meta charset='utf-8'>"
        "<style>*{margin:0;padding:0}"
        "iframe{border:none;width:100%;height:100%;position:fixed;inset:0}"
        "</style></head><body>"
        f"<iframe src='{inner_src}' title='Chat widget' allow='microphone'></iframe>"
        "<script>"
        "window.addEventListener('message',function(e){"
        "window.parent.postMessage(e.data,'*');"
        "});"
        "</script>"
        "</body></html>"
    )
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Security-Policy": f"frame-ancestors {origins}"},
    )


@router.patch("/config/{widget_id}", response_model=WidgetRead)
async def update_widget_config(
    widget_id: uuid.UUID,
    body: WidgetUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(current_admin),
) -> WidgetRead:
    """Admin only — update widget config from Streamlit admin page."""
    widget = await widget_repo.update(
        session, widget_id, **{k: v for k, v in body.model_dump().items() if v is not None}
    )
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found.")
    await session.commit()
    await session.refresh(widget)
    return WidgetRead.model_validate(widget)
