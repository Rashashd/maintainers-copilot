"""Vault client and secret cache.

All application secrets are loaded from Vault at startup via load_all().
Callers use the typed getters (get_db_password, get_llm_api_key, etc.).
Nothing secret lives in environment variables at runtime.
"""

import asyncio
from typing import Any

import hvac
import structlog

from app.core.config import get_settings

logger = structlog.get_logger()

# Module-level secret cache populated by load_all() at startup
_secrets: dict[str, Any] = {}


class VaultClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)

    def _read(self, path: str) -> dict:
        response = self._client.secrets.kv.v2.read_secret_version(
            path=path, raise_on_deleted_version=True
        )
        return response["data"]["data"]

    async def read(self, path: str) -> dict:
        return await asyncio.to_thread(self._read, path)

    async def write(self, path: str, **kv: str) -> None:
        await asyncio.to_thread(
            self._client.secrets.kv.v2.create_or_update_secret,
            path=path,
            secret=kv,
        )

    async def ping(self) -> bool:
        try:
            return bool(await asyncio.to_thread(self._client.is_authenticated))
        except Exception as exc:
            logger.warning("vault_ping_failed", error=str(exc))
            return False


_client: VaultClient | None = None


def get_vault_client() -> VaultClient:
    global _client
    if _client is None:
        _client = VaultClient()
    return _client


async def load_all() -> None:
    """Load all secrets from Vault into the module-level cache."""
    client = get_vault_client()
    paths = ["db", "minio", "jwt", "llm", "langfuse", "github"]
    for path in paths:
        try:
            _secrets[path] = await client.read(path)
            logger.info("secret_loaded", path=path)
        except Exception as exc:
            logger.warning("secret_load_failed", path=path, error=str(exc))
            _secrets[path] = {}


# ── Typed getters ─────────────────────────────────────────────────────────────

def get_db_password() -> str:
    return _secrets.get("db", {}).get("password", "")


def get_minio_access_key() -> str:
    return _secrets.get("minio", {}).get("access_key", "minioadmin")


def get_minio_secret_key() -> str:
    return _secrets.get("minio", {}).get("secret_key", "")


def get_jwt_signing_key() -> str:
    return _secrets.get("jwt", {}).get("signing_key", "")


def get_openai_api_key() -> str:
    return _secrets.get("llm", {}).get("openai_api_key", "")


def get_anthropic_api_key() -> str:
    return _secrets.get("llm", {}).get("anthropic_api_key", "")


def get_langfuse_keys() -> tuple[str, str, str]:
    d = _secrets.get("langfuse", {})
    return d.get("public_key", ""), d.get("secret_key", ""), d.get("host", "https://cloud.langfuse.com")


def get_github_token() -> str:
    return _secrets.get("github", {}).get("token", "")
