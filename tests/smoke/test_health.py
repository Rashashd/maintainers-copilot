"""Smoke tests — require a live stack (docker compose up).

Run with:
    SMOKE=1 pytest tests/smoke/ -v
"""

import os

import httpx
import pytest

API_URL = os.getenv("API_URL", "http://localhost:8000")


@pytest.mark.skipif(not os.getenv("SMOKE"), reason="set SMOKE=1 to run smoke tests")
def test_api_health():
    resp = httpx.get(f"{API_URL}/health", timeout=5)
    assert resp.status_code == 200


@pytest.mark.skipif(not os.getenv("SMOKE"), reason="set SMOKE=1 to run smoke tests")
def test_model_server_health():
    model_url = os.getenv("MODEL_URL", "http://localhost:8001")
    resp = httpx.get(f"{model_url}/health", timeout=5)
    assert resp.status_code == 200
