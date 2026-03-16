"""Zentrale Versionsquelle fuer Astra (M24).

Alle versions- und build-relevanten Informationen werden hier gepflegt.
Backend, Ops-Endpunkte und CLI beziehen die Version aus diesem Modul.
"""

import os
import subprocess
from datetime import datetime, timezone

# ── Astra Version (semantisch) ──────────────────────────
# Dies ist die EINZIGE Stelle, an der die Version gepflegt wird.
VERSION = "0.27.0-rc1"

# ── Build-Metadaten ─────────────────────────────────────
# Werden ueber Umgebungsvariablen oder Git-Informationen gefuellt.

BUILD_SHA = os.getenv("BUILD_SHA", None)
BUILD_DATE = os.getenv("BUILD_DATE", None)
BUILD_REF = os.getenv("BUILD_REF", None)  # z.B. Tag oder Branch


def get_git_sha() -> str | None:
    """Versucht den aktuellen Git-SHA zu lesen (best-effort)."""
    if BUILD_SHA:
        return BUILD_SHA
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_build_date() -> str:
    """Gibt das Build-Datum zurueck (Umgebungsvariable oder jetzt)."""
    if BUILD_DATE:
        return BUILD_DATE
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_version_info() -> dict:
    """Liefert alle Versions- und Build-Informationen.

    Sicher, nicht-sensitiv, fuer Ops- und Admin-Endpunkte geeignet.
    """
    return {
        "version": VERSION,
        "build_sha": get_git_sha(),
        "build_date": get_build_date(),
        "build_ref": BUILD_REF,
    }
