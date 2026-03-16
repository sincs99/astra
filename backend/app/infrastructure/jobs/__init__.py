"""Job-/Queue-Infrastruktur (M23).

Bietet eine saubere Abstraktion fuer Hintergrundarbeit:
- Jobs enqueuen
- Jobs ausfuehren
- Job-Status nachverfolgen
- Dev-/Test-Fallback (synchron) + Redis fuer Produktion
"""

from app.infrastructure.jobs.queue import enqueue_job, get_queue, set_queue
from app.infrastructure.jobs.registry import register_handler, get_handler
from app.infrastructure.jobs.models import JobRecord, JobStatus

__all__ = [
    "enqueue_job",
    "get_queue",
    "set_queue",
    "register_handler",
    "get_handler",
    "JobRecord",
    "JobStatus",
]
