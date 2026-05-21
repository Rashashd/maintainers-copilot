"""Registers all exception handlers on the FastAPI app.

Call register(app) once in main.py. Domain exceptions map to their HTTP status codes;
unhandled infrastructure exceptions become 500 with request_id but no stack trace.
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.schemas.errors import (
    InvalidRequest,
    NotFoundError,
    PermissionDenied,
    ToolFailure,
    WidgetOriginNotAllowed,
)

logger = structlog.get_logger()


def register(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(PermissionDenied)
    async def permission_denied_handler(request: Request, exc: PermissionDenied):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(WidgetOriginNotAllowed)
    async def widget_origin_handler(request: Request, exc: WidgetOriginNotAllowed):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(InvalidRequest)
    async def invalid_request_handler(request: Request, exc: InvalidRequest):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ToolFailure)
    async def tool_failure_handler(request: Request, exc: ToolFailure):
        # ToolFailure is normally caught inside the agent loop and fed back to the
        # LLM as a structured error. It only reaches here outside an agent context.
        return JSONResponse(
            status_code=502,
            content={"detail": str(exc), "tool": exc.tool},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = request.headers.get("X-Request-ID", "unknown")
        logger.error("unhandled_exception", request_id=request_id, error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )
