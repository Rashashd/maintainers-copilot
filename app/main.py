import uuid
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.core.exception_handlers import register as register_exception_handlers
from app.core.lifespan import lifespan
from app.routes import admin as admin_route
from app.routes import auth as auth_route
from app.routes import chat as chat_route
from app.routes import memory as memory_route
from app.routes import rag as rag_route
from app.routes import widget as widget_route

app = FastAPI(
    title="Maintainer's Co-Pilot",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened per widget at runtime via CSP frame-ancestors
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    structlog.contextvars.clear_contextvars()
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(auth_route.router)
app.include_router(chat_route.router)
app.include_router(memory_route.router)
app.include_router(rag_route.router)
app.include_router(widget_route.router)
app.include_router(admin_route.router)


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}


_WIDGET_JS = (Path(__file__).parent / "widget.js").read_text()


@app.get("/widget.js", include_in_schema=False)
async def widget_loader() -> Response:
    """Loader script — paste <script src='.../widget.js' data-widget-id='...'> into any page."""
    return Response(content=_WIDGET_JS, media_type="application/javascript")
