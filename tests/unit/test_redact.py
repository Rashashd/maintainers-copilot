"""Redaction layer tests.

Core guarantee: after redact(), none of the raw credential strings appear in the output.
These run on every push so a pattern regression is caught immediately.
"""

import pytest

from app.infra.redact import redact, redact_dict


@pytest.mark.parametrize(
    "raw, should_be_absent, expected_placeholder",
    [
        # OpenAI key
        (
            "key is sk-abcdefghijklmnopqrstuvwxyz123456 in the config",
            "sk-abcdefghijklmnopqrstuvwxyz123456",
            "<OPENAI_KEY>",
        ),
        # Anthropic key
        (
            "export ANTHROPIC_KEY=sk-ant-abcdefghijklmnopqrstuvwxyz12345678",
            "sk-ant-abcdefghijklmnopqrstuvwxyz12345678",
            "<ANTHROPIC_KEY>",
        ),
        # GitHub PAT (classic)
        (
            "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij",
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij",
            "<GITHUB_TOKEN>",
        ),
        # JWT
        (
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",  # noqa: E501
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "<JWT>",
        ),
        # Email
        (
            "Contact support at admin@example.com for help",
            "admin@example.com",
            "<EMAIL>",
        ),
        # Postgres DSN with password
        (
            "connecting to postgresql+asyncpg://copilot:supersecret@localhost:5432/db",
            "supersecret",
            "postgresql://<REDACTED>@",
        ),
        # Langfuse key
        (
            "pk-lf-abcdefghijklmnopqrstuvwxyz1234567890",
            "pk-lf-abcdefghijklmnopqrstuvwxyz1234567890",
            "<LANGFUSE_KEY>",
        ),
    ],
)
def test_redact_removes_secret(raw: str, should_be_absent: str, expected_placeholder: str) -> None:
    result = redact(raw)
    assert should_be_absent not in result, f"Secret still present after redaction: {result!r}"
    assert expected_placeholder in result, f"Expected placeholder missing: {result!r}"


def test_redact_plain_text_unchanged() -> None:
    text = "This is a normal GitHub issue about a KeyError in the config loader."
    assert redact(text) == text


def test_redact_dict_recurses() -> None:
    data = {
        "query": "show me issues from user@example.com",
        "meta": {"token": "sk-abcdefghijklmnopqrstuvwxyz123456"},
        "count": 5,
    }
    result = redact_dict(data)
    assert "user@example.com" not in str(result)
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in str(result)
    assert result["count"] == 5


def test_redact_dict_list_values() -> None:
    data = {"messages": ["hello admin@corp.io", "no secrets here"]}
    result = redact_dict(data)
    assert "admin@corp.io" not in str(result)
    assert result["messages"][1] == "no secrets here"
