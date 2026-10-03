"""Zeitstempel fuer API-Antworten (M49).

Die DateTime-Spalten liefern aus SQLite und PostgreSQL naive Werte (immer UTC) zurueck. `isoformat()`
haette dann keinen Zeitzonen-Suffix, und Browser lesen so einen String als Ortszeit. `iso_utc` liefert
deshalb immer UTC mit Suffix ("2026-10-03T12:00:00+00:00").
"""

from __future__ import annotations

from datetime import datetime, timezone


def iso_utc(value: datetime | None) -> str | None:
    """ISO-8601 in UTC mit "+00:00". Naive Werte gelten als UTC, aware werden nach UTC umgerechnet."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()
