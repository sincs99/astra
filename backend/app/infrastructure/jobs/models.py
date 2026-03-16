"""Job-Tracking-Modell (M23).

Leichtgewichtiges Modell fuer die Nachvollziehbarkeit von Hintergrundjobs.
"""

import uuid as _uuid
from datetime import datetime, timezone

from app.extensions import db


class JobStatus:
    """Moegliche Job-Statuswerte."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

    ALL = {PENDING, RUNNING, COMPLETED, FAILED, RETRYING}


class JobRecord(db.Model):
    """Persistentes Tracking fuer Hintergrundjobs."""
    __tablename__ = "job_records"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(
        db.String(36), unique=True, nullable=False,
        default=lambda: str(_uuid.uuid4()),
    )
    job_type = db.Column(db.String(64), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=JobStatus.PENDING, index=True)
    attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)

    # Payload (JSON) – keine Secrets speichern!
    payload_summary = db.Column(db.JSON, nullable=True)

    # Ergebnis / Fehler
    result = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)

    # Zeitstempel
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    scheduled_at = db.Column(db.DateTime, nullable=True)  # fuer verzoegerte Jobs

    def mark_running(self) -> None:
        """Setzt den Job auf 'running'."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        self.attempts = (self.attempts or 0) + 1

    def mark_completed(self, result: str | None = None) -> None:
        """Setzt den Job auf 'completed'."""
        self.status = JobStatus.COMPLETED
        self.finished_at = datetime.now(timezone.utc)
        self.result = result

    def mark_failed(self, error: str) -> None:
        """Setzt den Job auf 'failed' (alle Versuche aufgebraucht)."""
        self.status = JobStatus.FAILED
        self.finished_at = datetime.now(timezone.utc)
        self.error = error

    def mark_retrying(self, error: str) -> None:
        """Setzt den Job auf 'retrying' (wird erneut versucht)."""
        self.status = JobStatus.RETRYING
        self.error = error

    @property
    def can_retry(self) -> bool:
        """Prueft ob noch Versuche uebrig sind."""
        return (self.attempts or 0) < (self.max_attempts or 3)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "uuid": self.uuid,
            "job_type": self.job_type,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "payload_summary": self.payload_summary,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
        }

    def __repr__(self):
        return f"<JobRecord {self.job_type} [{self.status}]>"
