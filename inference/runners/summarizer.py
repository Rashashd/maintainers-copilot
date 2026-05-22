import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()

_MODEL_NAME = "sshleifer/distilbart-cnn-12-6"
_model: Any = None
_tokenizer: Any = None

# BART requires output shorter than input; bail out below this character count
_MIN_INPUT_CHARS = 100


def init_summarizer() -> None:
    global _model, _tokenizer
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    logger.info("loading_summarizer", model=_MODEL_NAME)
    _tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
    _model = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_NAME)
    _model.eval()
    logger.info("summarizer_ready")


async def summarize(text: str, max_sentences: int = 3) -> str:
    if len(text) < _MIN_INPUT_CHARS:
        return text.strip()

    if _model is None or _tokenizer is None:
        raise RuntimeError("Summarizer not initialized — call init_summarizer() first")

    max_tokens = max_sentences * 40
    min_tokens = max(10, max_sentences * 15)

    def _run() -> str:
        import torch
        inputs = _tokenizer(text, return_tensors="pt", truncation=True, max_length=1024)
        with torch.no_grad():
            output_ids = _model.generate(
                **inputs,
                max_length=max_tokens,
                min_length=min_tokens,
                num_beams=4,
                early_stopping=True,
            )
        return _tokenizer.decode(output_ids[0], skip_special_tokens=True)

    return (await asyncio.to_thread(_run)).strip()
