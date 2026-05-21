import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()

_MODEL_NAME = "sshleifer/distilbart-cnn-12-6"
_pipeline: Any = None

# BART requires output shorter than input; bail out below this character count
_MIN_INPUT_CHARS = 100


def init_summarizer() -> None:
    global _pipeline
    from transformers import pipeline  # noqa: PLC0415

    logger.info("loading_summarizer", model=_MODEL_NAME)
    _pipeline = pipeline(
        "summarization",
        model=_MODEL_NAME,
        tokenizer=_MODEL_NAME,
    )
    logger.info("summarizer_ready")


async def summarize(text: str, max_sentences: int = 3) -> str:
    if len(text) < _MIN_INPUT_CHARS:
        return text.strip()

    if _pipeline is None:
        raise RuntimeError("Summarizer not initialized — call init_summarizer() first")

    # Approximate token budget: ~40 tokens per sentence
    max_tokens = max_sentences * 40
    min_tokens = max(10, max_sentences * 15)

    result = await asyncio.to_thread(
        _pipeline,
        text,
        max_length=max_tokens,
        min_length=min_tokens,
        do_sample=False,
        truncation=True,
    )
    return result[0]["summary_text"].strip()
