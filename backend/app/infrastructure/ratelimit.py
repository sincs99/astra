"""Rate Limiting fuer Auth-Endpunkte.

Zaehlt Anfragen pro Schluessel in einem festen 60-Sekunden-Fenster.
Bei vorhandenem Redis (REDIS_URL) wird der Zaehler geteilt, sodass das Limit
auch bei mehreren Gunicorn-Workern gilt. Ohne erreichbares Redis faellt der
Limiter auf einen In-Memory-Zaehler pro Prozess zurueck.
"""

import logging
import time

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60

_memory_store: dict[str, list] = {}
_redis_client = None
_redis_url = None


def _get_redis(url: str):
    global _redis_client, _redis_url
    if _redis_url != url:
        _redis_url = url
        _redis_client = None
        try:
            import redis

            client = redis.Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)
            client.ping()
            _redis_client = client
        except Exception as exc:
            logger.warning("Rate Limiting: Redis nicht verfuegbar (%s), nutze In-Memory", exc)
    return _redis_client


def _hit_redis(client, key: str, limit: int) -> bool:
    bucket = int(time.time() // WINDOW_SECONDS)
    redis_key = f"ratelimit:{key}:{bucket}"
    pipe = client.pipeline()
    pipe.incr(redis_key)
    pipe.expire(redis_key, WINDOW_SECONDS * 2)
    count = pipe.execute()[0]
    return count <= limit


def _hit_memory(key: str, limit: int) -> bool:
    now = time.time()
    hits = [t for t in _memory_store.get(key, []) if now - t < WINDOW_SECONDS]
    if len(hits) >= limit:
        _memory_store[key] = hits
        return False
    hits.append(now)
    _memory_store[key] = hits
    return True


def allow(key: str, limit: int, redis_url: str | None = None) -> bool:
    """True, wenn die Anfrage noch im Limit liegt."""
    client = _get_redis(redis_url) if redis_url else None
    if client is not None:
        try:
            return _hit_redis(client, key, limit)
        except Exception as exc:
            logger.warning("Rate Limiting: Redis-Fehler (%s), nutze In-Memory", exc)
    return _hit_memory(key, limit)
