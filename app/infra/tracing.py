import logging

from langfuse import Langfuse, get_client, observe, propagate_attributes  # noqa: F401 — re-exported

logger = logging.getLogger(__name__)

_langfuse: Langfuse | None = None


def init_tracing(
    public_key: str, secret_key: str, host: str = "https://cloud.langfuse.com"
) -> Langfuse:
    global _langfuse
    _langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    return _langfuse


def get_langfuse() -> Langfuse:
    if _langfuse is None:
        raise RuntimeError("Tracing not initialised — call init_tracing() in lifespan first.")
    return _langfuse


async def ping_tracing() -> bool:
    try:
        lf = get_langfuse()
        lf.auth_check()  # raises if credentials are invalid or host unreachable
        return True
    except Exception as exc:
        logger.warning("Tracing ping failed: %s", exc)
        return False


__all__ = [
    "init_tracing", "get_langfuse", "ping_tracing", "observe", "get_client", "propagate_attributes",
]
