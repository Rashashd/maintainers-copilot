import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model: Any = None


def init_reranker() -> None:
    global _model
    from sentence_transformers import CrossEncoder  # noqa: PLC0415

    logger.info("loading_reranker", model=_MODEL_NAME)
    _model = CrossEncoder(_MODEL_NAME, max_length=512)
    logger.info("reranker_ready")


async def rerank(query: str, passages: list[str]) -> list[float]:
    if _model is None:
        raise RuntimeError("Reranker not initialized — call init_reranker() first")
    pairs = [(query, p) for p in passages]
    scores = await asyncio.to_thread(_model.predict, pairs)
    return [float(s) for s in scores]
