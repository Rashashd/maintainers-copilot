import hashlib
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI

from inference.routes import classify as classify_route
from inference.routes import ner as ner_route
from inference.routes import summarize as summarize_route
from inference.runners import classifier, ner, summarizer

MODEL_DIR = os.getenv("MODEL_DIR", "ml/finetune/output")
EXPECTED_SHA256_PATH = os.path.join(os.path.dirname(__file__), "expected_sha256.txt")
_weights_sha256: str = ""


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


def _compute_weights_sha256(model_dir: str) -> str:
    weights_file = Path(model_dir) / "model.safetensors"
    if not weights_file.exists():
        return ""
    h = hashlib.sha256()
    with open(weights_file, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _weights_sha256
    _configure_logging()
    actual = _compute_weights_sha256(MODEL_DIR)
    if not actual:
        raise RuntimeError(
            f"Classifier weights not found in {MODEL_DIR}/model.safetensors — cannot boot."
        )
    try:
        expected = Path(EXPECTED_SHA256_PATH).read_text().strip()
    except FileNotFoundError:
        raise RuntimeError(
            f"Expected SHA-256 file missing at {EXPECTED_SHA256_PATH}. "
            "Commit inference/expected_sha256.txt."
        )
    if actual != expected:
        raise RuntimeError(
            f"Classifier weights SHA-256 mismatch: expected {expected[:16]}… got {actual[:16]}…"
        )
    _weights_sha256 = actual
    classifier.init_classifier()
    ner.init_ner()
    summarizer.init_summarizer()
    yield


app = FastAPI(title="Inference Service", version="0.1.0", lifespan=lifespan)

app.include_router(classify_route.router)
app.include_router(ner_route.router)
app.include_router(summarize_route.router)


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {
        "status": "ok",
        "classifier": "loaded" if classifier._pipeline is not None else "not_loaded",
        "weights_sha256": _weights_sha256,
    }
