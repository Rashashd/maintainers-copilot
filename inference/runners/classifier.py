import asyncio
import os

import structlog

logger = structlog.get_logger()

MODEL_DIR = os.getenv("MODEL_DIR", "ml/finetune/output")

_pipeline = None


def init_classifier() -> None:
    global _pipeline
    from transformers import pipeline  # noqa: PLC0415

    logger.info("loading_classifier", model_dir=MODEL_DIR)
    _pipeline = pipeline(
        "text-classification",
        model=MODEL_DIR,
        tokenizer=MODEL_DIR,
        top_k=None,
        device=-1,
        truncation=True,
        max_length=128,
    )
    logger.info("classifier_ready")


async def classify(title: str, body: str) -> dict:
    if _pipeline is None:
        raise RuntimeError("Classifier not initialized — call init_classifier() first")
    text = f"{title} [SEP] {body}"
    results = await asyncio.to_thread(_pipeline, text)
    # normalize: pipeline returns flat list for single string input
    items: list = results[0] if results and isinstance(results[0], list) else results
    scores = {item["label"]: round(float(item["score"]), 4) for item in items}
    label = max(scores, key=scores.__getitem__)
    return {"label": label, "scores": scores}
