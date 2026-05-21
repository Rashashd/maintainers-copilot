"""Refuse-to-boot guarantees. All five checks must pass or the process exits."""

import structlog
import yaml

from app.core.config import get_settings
from app.infra.redis import ping_redis
from app.infra.tracing import ping_tracing
from app.infra.vault import get_anthropic_api_key, get_langfuse_keys, get_openai_api_key, get_vault_client

logger = structlog.get_logger()


class VaultUnreachable(RuntimeError):
    pass


class TracingMisconfigured(RuntimeError):
    pass


class EvalThresholdsDisabled(RuntimeError):
    pass


class NoLLMKeyConfigured(RuntimeError):
    pass


class RedisUnreachable(RuntimeError):
    pass


async def assert_vault_reachable() -> None:
    client = get_vault_client()
    if not await client.ping():
        raise VaultUnreachable("Vault is unreachable or token is invalid. Cannot boot without secrets.")


async def assert_tracing_configured() -> None:
    pub, sec, _ = get_langfuse_keys()
    if not pub or not sec:
        logger.warning("tracing_disabled", reason="langfuse_keys_not_set_in_vault")
        return
    if not await ping_tracing():
        raise TracingMisconfigured("Tracing backend rejected the startup ping. Cannot boot blind.")


def assert_eval_thresholds_nonzero() -> None:
    settings = get_settings()
    try:
        with open(settings.eval_thresholds_path) as f:
            thresholds = yaml.safe_load(f)
    except FileNotFoundError:
        raise EvalThresholdsDisabled(f"eval_thresholds.yaml not found at {settings.eval_thresholds_path}")

    def _walk(node: object, path: str = "") -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, f"{path}.{k}" if path else k)
        elif node in (0, 0.0, None, False, ""):
            raise EvalThresholdsDisabled(f"Threshold '{path}' is zero or disabled — eval gate is off.")

    _walk(thresholds)


def assert_llm_key_configured() -> None:
    if not get_openai_api_key() and not get_anthropic_api_key():
        raise NoLLMKeyConfigured(
            "No LLM API key found in Vault (neither openai_api_key nor anthropic_api_key). "
            "Run: vault kv put secret/llm openai_api_key=<key>"
        )
    primary = "openai" if get_openai_api_key() else "anthropic (fallback only)"
    logger.info("llm_provider_active", provider=primary)


async def assert_redis_reachable() -> None:
    if not await ping_redis():
        raise RedisUnreachable("Redis is unreachable. Cannot boot without short-term memory.")


async def run_startup_checks() -> None:
    logger.info("startup_checks_starting")
    await assert_vault_reachable()
    await assert_redis_reachable()
    await assert_tracing_configured()
    assert_llm_key_configured()
    assert_eval_thresholds_nonzero()
    logger.info("startup_checks_passed")
