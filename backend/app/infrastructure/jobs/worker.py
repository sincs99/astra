"""Queue-Worker (M23).

Verarbeitet Jobs aus der Redis-Queue.
Kann als separater Prozess gestartet werden.

Verwendung:
    python cli.py worker [--poll-interval 1]
"""

from __future__ import annotations

import json
import logging
import signal
import time

logger = logging.getLogger(__name__)

_running = True


def _handle_signal(signum, frame):
    """Graceful Shutdown bei SIGINT/SIGTERM."""
    global _running
    _running = False
    logger.info("Worker: Shutdown-Signal empfangen, beende nach aktuellem Job...")


def run_worker(app, poll_interval: float = 1.0) -> None:
    """Startet den Worker-Loop.

    Args:
        app: Flask-App-Instanz fuer App-Kontext
        poll_interval: Sekunden zwischen Queue-Polls
    """
    global _running
    _running = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("Worker gestartet (poll_interval=%ss)", poll_interval)

    with app.app_context():
        # Handler registrieren
        from app.infrastructure.jobs.handlers import setup_handlers
        setup_handlers()

        try:
            import redis as redis_lib
        except ImportError:
            logger.error("redis-Paket nicht installiert. Worker benoetigt Redis.")
            return

        redis_url = app.config.get("REDIS_URL", "redis://localhost:6379/0")

        try:
            r = redis_lib.from_url(redis_url)
            r.ping()
            logger.info("Worker: Redis-Verbindung OK (%s)", redis_url)
        except Exception as e:
            logger.error("Worker: Redis-Verbindung fehlgeschlagen: %s", e)
            return

        from app.infrastructure.jobs.queue import _execute_job, RedisQueue
        from app.infrastructure.jobs.models import JobRecord
        from app.extensions import db

        while _running:
            try:
                # Blockierendes Pop mit Timeout
                result = r.brpop(RedisQueue.QUEUE_KEY, timeout=int(poll_interval))
                if result is None:
                    continue

                _, raw = result
                message = json.loads(raw)
                job_id = message.get("job_id")
                payload = message.get("payload", {})

                job_record = db.session.get(JobRecord, job_id)
                if not job_record:
                    logger.warning("Worker: Job %s nicht in DB gefunden", job_id)
                    continue

                logger.info("Worker: Verarbeite Job %s [%s]",
                            job_record.uuid, job_record.job_type)
                _execute_job(job_record, payload)

            except Exception as e:
                logger.error("Worker: Fehler bei Job-Verarbeitung: %s", e)
                time.sleep(poll_interval)

    logger.info("Worker beendet")
