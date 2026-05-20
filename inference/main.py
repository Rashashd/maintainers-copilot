import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from inference.routes import classify as classify_route
from inference.routes import ner as ner_route
from inference.routes import summarize as summarize_route
from inference.runners import classifier, ner


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    classifier.init_classifier()
    ner.init_ner()
    yield


app = FastAPI(title="Inference Service", version="0.1.0", lifespan=lifespan)

app.include_router(classify_route.router)
app.include_router(ner_route.router)
app.include_router(summarize_route.router)


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}
