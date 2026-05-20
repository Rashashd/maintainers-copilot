import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()

NER_MODEL = "dslim/bert-base-NER"

_pipeline: Any = None


def init_ner() -> None:
    global _pipeline
    try:
        from transformers import pipeline  # noqa: PLC0415

        logger.info("loading_ner", model=NER_MODEL)
        _pipeline = pipeline(
            "ner",
            model=NER_MODEL,
            aggregation_strategy="simple",  # type: ignore[call-arg]
            device=-1,
        )
        logger.info("ner_ready")
    except Exception as exc:
        logger.warning("ner_load_failed", error=str(exc))


async def extract_entities(text: str) -> list[dict]:
    if _pipeline is None:
        raise RuntimeError("NER runner not available")
    results = await asyncio.to_thread(_pipeline, text[:1000])
    return [
        {
            "text": r["word"],
            "label": r["entity_group"],
            "score": round(float(r["score"]), 4),
            "start": r["start"],
            "end": r["end"],
        }
        for r in results
    ]
