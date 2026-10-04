"""Aufraeumen alter Job-Eintraege (nur abgeschlossene und endgueltig fehlgeschlagene)."""

from datetime import datetime, timedelta

from app.extensions import db
from app.infrastructure.jobs.models import JobRecord, JobStatus

DEFAULT_RETENTION_DAYS = 30


def cleanup_jobs(days: int = DEFAULT_RETENTION_DAYS, dry_run: bool = False, now: datetime | None = None) -> dict:
    """Loescht `completed`- und `failed`-Jobs, die vor mehr als `days` Tagen beendet wurden.

    Laufende, wartende und wiederholte Jobs bleiben immer erhalten. `finished_at` fehlt nie bei
    beendeten Jobs; ohne Wert wird der Job nicht angefasst.
    """
    if days < 1:
        raise ValueError("days muss mindestens 1 sein")
    cutoff = (now or datetime.utcnow()) - timedelta(days=days)
    query = JobRecord.query.filter(
        JobRecord.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]),
        JobRecord.finished_at.isnot(None),
        JobRecord.finished_at < cutoff,
    )
    count = query.count()
    if count and not dry_run:
        query.delete(synchronize_session=False)
        db.session.commit()
    return {"deleted": 0 if dry_run else count, "matched": count, "dry_run": dry_run, "days": days}
