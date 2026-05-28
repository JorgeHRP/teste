import json
from typing import Any
from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_redis = None


def _get_redis():
    global _redis
    if _redis is None and settings.REDIS_URL:
        try:
            import redis
            _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _redis.ping()
            logger.info("Redis conectado.")
        except Exception as e:
            logger.warning(f"Redis indisponível, cache desativado: {e}")
            _redis = False
    return _redis if _redis else None


async def cache_get(key: str) -> Any | None:
    r = _get_redis()
    if not r:
        return None
    try:
        value = r.get(key)
        return json.loads(value) if value else None
    except Exception as e:
        logger.warning(f"Erro ao ler cache [{key}]: {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int = None) -> None:
    r = _get_redis()
    if not r:
        return
    ttl = ttl or settings.CACHE_TTL_SECONDS
    try:
        r.setex(key, ttl, json.dumps(value))
    except Exception as e:
        logger.warning(f"Erro ao escrever cache [{key}]: {e}")


async def cache_delete(key: str) -> None:
    r = _get_redis()
    if not r:
        return
    try:
        r.delete(key)
    except Exception as e:
        logger.warning(f"Erro ao apagar cache [{key}]: {e}")
