"""Rate Limiting fuer Auth-Endpunkte.

Zaehlt Anfragen pro Schluessel in einem festen Zeitfenster (Standard 60 Sekunden, M71: auch Stunden).
Bei vorhandenem Redis (REDIS_URL) wird der Zaehler geteilt, sodass das Limit
auch bei mehreren Gunicorn-Workern gilt. Ohne erreichbares Redis faellt der
Limiter auf einen In-Memory-Zaehler pro Prozess zurueck.
"""

import logging
import math
import time

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60
HOUR_SECONDS = 3600

_memory_store: dict[str, list] = {}
_redis_client = None
_redis_url = None


def reset_memory() -> None:
    """Leert den In-Memory-Zaehler (fuer Tests)."""
    _memory_store.clear()


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


def _redis_key(key: str, window: int) -> str:
    return f"ratelimit:{key}:{window}:{int(time.time() // window)}"


def _hit_redis(client, key: str, limit: int, window: int) -> tuple[bool, int]:
    pipe = client.pipeline()
    redis_key = _redis_key(key, window)
    pipe.incr(redis_key)
    pipe.expire(redis_key, window * 2)
    count = pipe.execute()[0]
    return count <= limit, window - int(time.time() % window)


def _hit_memory(key: str, limit: int, window: int) -> tuple[bool, int]:
    now = time.time()
    hits = [t for t in _memory_store.get(key, []) if now - t < window]
    if len(hits) >= limit:
        _memory_store[key] = hits
        return False, max(math.ceil(hits[0] + window - now), 1)
    hits.append(now)
    _memory_store[key] = hits
    return True, 0


def hit(key: str, limit: int, window: int = WINDOW_SECONDS, redis_url: str | None = None) -> tuple[bool, int]:
    """Zaehlt einen Treffer. Rueckgabe: (erlaubt, retry_after_seconds); retry_after ist bei erlaubt 0."""
    client = _get_redis(redis_url) if redis_url else None
    if client is not None:
        try:
            ok, retry = _hit_redis(client, key, limit, window)
            return ok, (0 if ok else retry)
        except Exception as exc:
            logger.warning("Rate Limiting: Redis-Fehler (%s), nutze In-Memory", exc)
    return _hit_memory(key, limit, window)


def blocked(key: str, limit: int, window: int, redis_url: str | None = None) -> tuple[bool, int]:
    """Ist der Schluessel gesperrt (mindestens `limit` Treffer im Fenster)? Zaehlt nicht mit. (gesperrt, retry_after)."""
    client = _get_redis(redis_url) if redis_url else None
    if client is not None:
        try:
            count = int(client.get(_redis_key(key, window)) or 0)
            return count >= limit, window - int(time.time() % window)
        except Exception as exc:
            logger.warning("Rate Limiting: Redis-Fehler (%s), nutze In-Memory", exc)
    now = time.time()
    hits = [t for t in _memory_store.get(key, []) if now - t < window]
    if len(hits) >= limit:
        return True, max(math.ceil(hits[0] + window - now), 1)
    return False, 0


def record(key: str, window: int, redis_url: str | None = None) -> None:
    """Zaehlt einen Treffer ohne Limitpruefung (z.B. Fehlversuch)."""
    hit(key, 10 ** 9, window, redis_url)


def allow(key: str, limit: int, redis_url: str | None = None) -> bool:
    """True, wenn die Anfrage noch im Limit liegt (60-Sekunden-Fenster)."""
    return hit(key, limit, WINDOW_SECONDS, redis_url)[0]


def limited_response(retry_after: int):
    """429-Antwort im einheitlichen Format: {error, code: "rate_limited", retry_after_seconds} plus Retry-After."""
    from flask import jsonify
    retry_after = max(int(retry_after), 1)
    resp = jsonify({"error": "Zu viele Anfragen, bitte später erneut versuchen",
                    "code": "rate_limited", "retry_after_seconds": retry_after})
    resp.status_code = 429
    resp.headers["Retry-After"] = str(retry_after)
    return resp
