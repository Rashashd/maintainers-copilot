"""Tests for POST /rag/ask."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_rag_ask_returns_answer(client):
    with patch(
        "app.routes.rag.rag_service.answer",
        new_callable=AsyncMock,
        return_value=("Yes, per #1234.", ["context chunk 1"]),
    ):
        resp = await client.post("/rag/ask", json={"query": "How do I configure auth?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Yes, per #1234."
    assert body["query"] == "How do I configure auth?"
    assert body["contexts"] == ["context chunk 1"]


@pytest.mark.asyncio
async def test_rag_ask_empty_query_rejected(client):
    resp = await client.post("/rag/ask", json={"query": "   "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rag_ask_alpha_default(client):
    with patch(
        "app.routes.rag.rag_service.answer",
        new_callable=AsyncMock,
        return_value=("answer", []),
    ) as mock_answer:
        await client.post("/rag/ask", json={"query": "What is Home Assistant?"})

    _, kwargs = mock_answer.call_args
    positional_alpha = mock_answer.call_args[0][2] if len(mock_answer.call_args[0]) > 2 else 0.6
    assert kwargs.get("alpha", positional_alpha) == 0.6


@pytest.mark.asyncio
async def test_rag_ask_custom_alpha(client):
    with patch(
        "app.routes.rag.rag_service.answer",
        new_callable=AsyncMock,
        return_value=("answer", []),
    ) as mock_answer:
        await client.post("/rag/ask", json={"query": "question", "alpha": 0.3})

    call_args = mock_answer.call_args
    assert 0.3 in call_args[0] or call_args[1].get("alpha") == 0.3
