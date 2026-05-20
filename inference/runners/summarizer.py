import re


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in parts if len(s.strip()) > 20]


def summarize(text: str, max_sentences: int = 3) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return text[:500].strip()
    return " ".join(sentences[:max_sentences])
