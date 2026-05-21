"""Redaction layer — must run before any string leaves the service via logs, traces, or memory.

Call redact(text) on any user content, LLM I/O, or tool arguments before they are logged
or written as span attributes. Patterns are conservative: they match known credential shapes
and common PII formats without trying to parse arbitrary free text.
"""

import re
from typing import Any

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Anthropic key must come before the generic sk- pattern (sk-ant- is a subset)
    (re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"), "<ANTHROPIC_KEY>"),
    (re.compile(r"sk-[A-Za-z0-9\-_]{20,}"), "<OPENAI_KEY>"),
    # GitHub personal access tokens (classic and fine-grained)
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "<GITHUB_TOKEN>"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{82}"), "<GITHUB_TOKEN>"),
    # JWTs (header.payload.signature)
    (re.compile(r"eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"), "<JWT>"),
    # AWS-style access keys
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<AWS_KEY>"),
    # Generic Bearer tokens in Authorization headers
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{20,}", re.IGNORECASE), "Bearer <TOKEN>"),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "<EMAIL>"),
    # Absolute Unix home-directory paths (e.g. /home/user/... or /Users/user/...)
    (re.compile(r"/(home|Users)/[^/\s]+"), "/<HOME_DIR>"),
    # Windows home paths
    (re.compile(r"C:\\\\Users\\\\[^\\\\s]+", re.IGNORECASE), r"C:\\Users\\<USER>"),
    # Postgres connection strings with embedded password
    (re.compile(r"postgresql(\+\w+)?://[^:]+:[^@]+@"), "postgresql://<REDACTED>@"),
    # Langfuse / generic secret keys that look like pk-lf-* or sk-lf-*
    (re.compile(r"[ps]k-lf-[A-Za-z0-9\-_]{20,}"), "<LANGFUSE_KEY>"),
]


def redact(text: str) -> str:
    """Apply all redaction patterns to text. Returns the sanitised string."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact all string values in a dict (for span attributes / log fields)."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, str):
            out[k] = redact(v)
        elif isinstance(v, dict):
            out[k] = redact_dict(v)
        elif isinstance(v, list):
            out[k] = [redact(i) if isinstance(i, str) else i for i in v]
        else:
            out[k] = v
    return out
