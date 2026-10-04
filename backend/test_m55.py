"""M55 – Aufraeumen alter Job-Eintraege (cleanup_jobs und CLI cleanup-jobs)."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.infrastructure.jobs.cleanup import cleanup_jobs
from app.infrastructure.jobs.models import JobRecord, JobStatus

passed = 0
failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  OK  {label}")
    else:
        failed += 1
        print(f"  FAIL {label}" + (f" – {detail}" if detail else ""))


NOW = datetime(2026, 10, 4, 12, 0, 0)
app = create_app("testing")


def add(job_type, status, finished_days_ago=None):
    j = JobRecord(job_type=job_type, status=status)
    if finished_days_ago is not None:
        j.finished_at = NOW - timedelta(days=finished_days_ago)
    db.session.add(j)
    db.session.commit()


def types():
    return sorted(j.job_type for j in JobRecord.query.all())


with app.app_context():
    db.create_all()
    add("old_done", JobStatus.COMPLETED, 40)
    add("old_failed", JobStatus.FAILED, 31)
    add("recent_done", JobStatus.COMPLETED, 5)
    add("recent_failed", JobStatus.FAILED, 29)
    add("old_pending", JobStatus.PENDING)
    add("old_running", JobStatus.RUNNING)
    add("old_retrying", JobStatus.RETRYING)
    add("done_no_time", JobStatus.COMPLETED)
    add("requeued_old", JobStatus.RETRYING, 90)  # erneut eingereihter Job mit altem finished_at

    print("Trockenlauf")
    res = cleanup_jobs(30, dry_run=True, now=NOW)
    check("zaehlt zwei Treffer, loescht nichts", res["matched"] == 2 and res["deleted"] == 0 and len(types()) == 9, str(res))

    print("Aufraeumen")
    res = cleanup_jobs(30, now=NOW)
    check("loescht alte completed und failed", res["deleted"] == 2 and "old_done" not in types() and "old_failed" not in types(), str(res))
    check("junge Jobs bleiben", {"recent_done", "recent_failed"} <= set(types()))
    check("pending, running, retrying bleiben, auch ohne Endzeit", {"old_pending", "old_running", "old_retrying", "done_no_time", "requeued_old"} <= set(types()))
    check("idempotent: zweiter Lauf loescht nichts", cleanup_jobs(30, now=NOW)["deleted"] == 0)

    print("Aufbewahrungsdauer")
    res = cleanup_jobs(3, now=NOW)
    check("3 Tage: auch recent_done und recent_failed weg", res["deleted"] == 2 and "recent_done" not in types())
    try:
        cleanup_jobs(0)
        ok = False
    except ValueError:
        ok = True
    check("days < 1 wird abgelehnt", ok)

print("CLI cleanup-jobs")
with tempfile.TemporaryDirectory() as tmp:
    db_path = f"{tmp}/t.db"
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{db_path}", "RUNNER_ADAPTER": "stub"}
    cwd = os.path.dirname(__file__)
    subprocess.run([sys.executable, "-c",
                    "from datetime import datetime, timedelta\n"
                    "from app import create_app;from app.extensions import db\n"
                    "from app.infrastructure.jobs.models import JobRecord\n"
                    "a=create_app()\n"
                    "with a.app_context():\n"
                    "    db.create_all()\n"
                    "    old=datetime.utcnow()-timedelta(days=60)\n"
                    "    db.session.add(JobRecord(job_type='x',status='completed',finished_at=old))\n"
                    "    db.session.add(JobRecord(job_type='y',status='pending'))\n"
                    "    db.session.commit()"], env=env, capture_output=True, check=True, cwd=cwd)
    dry = subprocess.run([sys.executable, "cli.py", "cleanup-jobs", "--dry-run"], env=env, capture_output=True, text=True, cwd=cwd)
    rows_dry = sqlite3.connect(db_path).execute("select count(*) from job_records").fetchone()[0]
    out = subprocess.run([sys.executable, "cli.py", "cleanup-jobs", "--days", "30"], env=env, capture_output=True, text=True, cwd=cwd)
    rows = sqlite3.connect(db_path).execute("select count(*) from job_records").fetchone()[0]
    bad = subprocess.run([sys.executable, "cli.py", "cleanup-jobs", "--days", "0"], env=env, capture_output=True, text=True, cwd=cwd)
check("--dry-run: Exit 0, nichts geloescht", dry.returncode == 0 and rows_dry == 2 and json.loads(dry.stdout.splitlines()[-1])["matched"] == 1, dry.stderr[-200:])
check("CLI loescht den alten Job, der wartende bleibt", out.returncode == 0 and rows == 1
      and json.loads(out.stdout.splitlines()[-1])["deleted"] == 1, out.stdout[-200:] + out.stderr[-200:])
check("--days 0: Exit 2", bad.returncode == 2, str(bad.returncode))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
