import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()

_MODEL_NAME = "BAAI/bge-base-en-v1.5"
# BGE requires this prefix on queries only; documents are encoded as-is
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_model: Any = None


def init_embedder() -> None:
    global _model
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    logger.info("loading_embedder", model=_MODEL_NAME)
    _model = SentenceTransformer(_MODEL_NAME)
    logger.info("embedder_ready")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed documents (no query prefix)."""
    if _model is None:
        raise RuntimeError("Embedder not initialized — call init_embedder() first")
    vectors = await asyncio.to_thread(_model.encode, texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


async def embed_query(query: str) -> list[float]:
    """Embed a search query (BGE query prefix applied)."""
    if _model is None:
        raise RuntimeError("Embedder not initialized — call init_embedder() first")
    prefixed = _QUERY_PREFIX + query
    vectors = await asyncio.to_thread(_model.encode, [prefixed], normalize_embeddings=True)
    return vectors[0].tolist()
