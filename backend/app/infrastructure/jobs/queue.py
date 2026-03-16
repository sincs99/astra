"""Queue-Abstraktion (M23).

Zwei Backends:
- SyncQueue: Fuehrt Jobs sofort synchron aus (Dev/Test)
- RedisQueue: Sendet Jobs an Redis fuer asynchrone Verarbeitung (Produktion)

Design:
- enqueue_job() ist der zentrale Einstiegspunkt
- Erstellt immer einen JobRecord in der DB
- Delegiert die Ausfuehrung/Einreihung an das aktive Backend
"""

from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.infrastructure.jobs.models import JobRecord, JobStatus
from app.infrastructure.jobs.registry import get_handler

logger = logging.getLogger(__name__)


# ── Queue-Interface ─────────────────────────────────────


class QueueBackend(ABC):
    """Abstraktes Interface fuer Queue-Backends."""

    @abstractmethod
    def push(self, job_record: JobRecord, payload: dict) -> None:
        """Reiht einen Job zur Verarbeitung ein."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Name des Backends fuer Logging/Info."""
        ...


# ── Sync Queue (Dev/Test) ──────────────────────────────


class SyncQueue(QueueBackend):
    """Fuehrt Jobs sofort synchron aus. Fuer Dev und Tests."""

    def name(self) -> str:
        return "sync"

    def push(self, job_record: JobRecord, payload: dict) -> None:
        """Fuehrt den Job sofort im aktuellen Thread aus."""
        _execute_job(job_record, payload)


# ── Thread Queue (Dev mit non-blocking) ─────────────────


class ThreadQueue(QueueBackend):
    """Fuehrt Jobs in einem Daemon-Thread aus. Non-blocking Dev-Modus."""

    def name(self) -> str:
        return "thread"

    def push(self, job_record: JobRecord, payload: dict) -> None:
        """Startet einen Thread fuer den Job."""
        try:
            from flask import current_app
            app = current_app._get_current_object()
        except RuntimeError:
            # Kein App-Kontext - synchron ausfuehren
            _execute_job(job_record, payload)
            return

        thread = threading.Thread(
            target=self._run_in_context,
            args=(app, job_record.id, payload),
            daemon=True,
        )
        thread.start()

    def _run_in_context(self, app, job_id: int, payload: dict) -> None:
        """Fuehrt den Job mit App-Kontext aus."""
        with app.app_context():
            job_record = db.session.get(JobRecord, job_id)
            if job_record:
                _execute_job(job_record, payload)


# ── Redis Queue (Produktion) ───────────────────────────


class RedisQueue(QueueBackend):
    """Sendet Jobs an eine Redis-Queue fuer Worker-Verarbeitung."""

    QUEUE_KEY = "astra:jobs:pending"

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._redis_url = redis_url
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(self._redis_url)
            except ImportError:
                logger.warning("redis-Paket nicht installiert - Fallback auf Sync")
                return None
            except Exception as e:
                logger.warning("Redis-Verbindung fehlgeschlagen: %s - Fallback auf Sync", e)
                return None
        return self._redis

    def name(self) -> str:
        return "redis"

    def push(self, job_record: JobRecord, payload: dict) -> None:
        """Sendet Job-ID an Redis-Queue."""
        r = self._get_redis()
        if r is None:
            # Fallback: synchron
            logger.debug("Redis nicht verfuegbar - Job %s synchron ausfuehren", job_record.uuid)
            _execute_job(job_record, payload)
            return

        try:
            message = json.dumps({
                "job_id": job_record.id,
                "job_uuid": job_record.uuid,
                "job_type": job_record.job_type,
                "payload": payload,
            })
            r.lpush(self.QUEUE_KEY, message)
            logger.debug("Job %s an Redis-Queue gesendet", job_record.uuid)
        except Exception as e:
            logger.error("Redis push fehlgeschlagen: %s - Job synchron ausfuehren", e)
            _execute_job(job_record, payload)


# ── Globale Queue-Instanz ──────────────────────────────

_queue: QueueBackend | None = None


def get_queue() -> QueueBackend:
    """Gibt das aktive Queue-Backend zurueck."""
    global _queue
    if _queue is None:
        _queue = SyncQueue()
    return _queue


def set_queue(queue: QueueBackend) -> None:
    """Setzt das aktive Queue-Backend."""
    global _queue
    _queue = queue
    logger.info("Queue-Backend gesetzt: %s", queue.name())


# ── Zentraler Einstiegspunkt ────────────────────────────


def enqueue_job(
    job_type: str,
    payload: dict | None = None,
    max_attempts: int = 3,
    delay_seconds: int = 0,
    payload_summary: dict | None = None,
) -> JobRecord:
    """Erstellt einen Job, speichert ihn in der DB und reiht ihn ein.

    Args:
        job_type: Typ des Jobs (aus registry)
        payload: Volle Payload fuer den Handler (wird NICHT in DB gespeichert)
        max_attempts: Maximale Ausfuehrungsversuche
        delay_seconds: Verzoegerung in Sekunden
        payload_summary: Zusammenfassung fuer DB-Tracking (keine Secrets!)

    Returns:
        Der erstellte JobRecord
    """
    payload = payload or {}

    # Payload-Summary erzeugen wenn nicht angegeben
    if payload_summary is None:
        payload_summary = _safe_summary(job_type, payload)

    # JobRecord in DB anlegen
    job = JobRecord(
        job_type=job_type,
        status=JobStatus.PENDING,
        max_attempts=max_attempts,
        payload_summary=payload_summary,
    )

    if delay_seconds > 0:
        job.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

    db.session.add(job)
    db.session.commit()

    logger.info("Job erstellt: %s [%s] (max=%d, delay=%ds)",
                job.uuid, job_type, max_attempts, delay_seconds)

    # An Queue senden
    queue = get_queue()
    queue.push(job, payload)

    return job


# ── Job-Ausfuehrung ────────────────────────────────────


def _execute_job(job_record: JobRecord, payload: dict) -> None:
    """Fuehrt einen einzelnen Job aus mit Fehlerbehandlung."""
    handler = get_handler(job_record.job_type)
    if handler is None:
        error_msg = f"Kein Handler fuer Job-Typ: {job_record.job_type}"
        logger.error(error_msg)
        job_record.mark_failed(error_msg)
        db.session.commit()
        return

    # Verzoegerte Jobs: scheduled_at pruefen
    if job_record.scheduled_at:
        now = datetime.now(timezone.utc)
        sched = job_record.scheduled_at
        if sched.tzinfo is None:
            sched = sched.replace(tzinfo=timezone.utc)
        delay = (sched - now).total_seconds()
        if delay > 0:
            import time
            logger.debug("Job %s: warte %ds bis scheduled_at", job_record.uuid, delay)
            time.sleep(delay)

    job_record.mark_running()
    db.session.commit()

    try:
        result = handler(payload)
        job_record.mark_completed(result)
        db.session.commit()
        logger.info("Job %s [%s] erfolgreich (Versuch %d/%d)",
                     job_record.uuid, job_record.job_type,
                     job_record.attempts, job_record.max_attempts)
    except Exception as e:
        error_msg = str(e)
        # Keine Secrets in Logs leaken
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        logger.warning("Job %s [%s] fehlgeschlagen (Versuch %d/%d): %s",
                        job_record.uuid, job_record.job_type,
                        job_record.attempts, job_record.max_attempts, error_msg)

        if job_record.can_retry:
            job_record.mark_retrying(error_msg)
            db.session.commit()
            # Retry
            _execute_job(job_record, payload)
        else:
            job_record.mark_failed(error_msg)
            db.session.commit()
            logger.error("Job %s [%s] endgueltig fehlgeschlagen nach %d Versuchen",
                          job_record.uuid, job_record.job_type, job_record.attempts)


def _safe_summary(job_type: str, payload: dict) -> dict:
    """Erzeugt eine sichere Zusammenfassung ohne Secrets."""
    summary = {"job_type": job_type}
    # Nur bekannte sichere Felder uebernehmen
    safe_keys = {"event", "webhook_id", "routine_id", "instance_id",
                 "instance_uuid", "agent_id", "action_type", "sequence"}
    for key in safe_keys:
        if key in payload:
            summary[key] = payload[key]
    return summary
