"""Aktive Admin-Benachrichtigung (M58): Mail und/oder Webhook, entprellt ueber `system_state`.

Kanaele (beide optional, leer = aus):
- `ADMIN_ALERT_EMAIL`: eine oder mehrere Adressen, kommagetrennt
- `ADMIN_ALERT_WEBHOOK_URL`: JSON-POST mit `content` (Discord), `text` (Slack) und `subject`

Entprellen: Ein Ausloeser (`key`) meldet sich beim Wechsel gesund -> gestoert und danach hoechstens einmal
pro `ADMIN_ALERT_COOLDOWN_MINUTES`, solange er gestoert bleibt. Wird er wieder gesund, geht optional einmal
eine Entwarnung raus (`ADMIN_ALERT_RECOVERY`). Alles ist best effort: Fehler beim Versenden werden nur
geloggt und stoeren weder den Billing-Tick noch Webhooks. Die Webhook-URL enthaelt oft ein Geheimnis und
wird deshalb nie geloggt.
"""

import logging
from datetime import datetime

import requests
from flask import current_app

from app.extensions import db
from app.utils.timeutil import iso_utc

logger = logging.getLogger(__name__)

STATE_PREFIX = "alert:"
WEBHOOK_TIMEOUT_SECONDS = 5
_MAX_TEXT = 1900  # Discord erlaubt 2000 Zeichen


def _now() -> datetime:
    return datetime.utcnow()


def configured_channels() -> dict:
    cfg = current_app.config
    emails = [a.strip() for a in (cfg.get("ADMIN_ALERT_EMAIL") or "").split(",") if a.strip()]
    return {"email": emails, "webhook": bool((cfg.get("ADMIN_ALERT_WEBHOOK_URL") or "").strip())}


def send_admin_alert(subject: str, message: str) -> dict:
    """Sendet an alle konfigurierten Kanaele. Rueckgabe je Kanal: True/False, None = nicht konfiguriert."""
    channels = configured_channels()
    result = {"email": None, "webhook": None}

    if channels["email"]:
        from app.infrastructure.mail import send_mail
        ok = True
        for addr in channels["email"]:
            try:
                ok = bool(send_mail(current_app, addr, subject, message)) and ok
            except Exception:
                ok = False
                logger.exception("Admin-Alert: Mail an %s fehlgeschlagen", addr)
        result["email"] = ok

    if channels["webhook"]:
        url = current_app.config["ADMIN_ALERT_WEBHOOK_URL"].strip()
        text = f"**{subject}**\n{message}"[:_MAX_TEXT]
        try:
            resp = requests.post(url, json={"content": text, "text": text, "subject": subject},
                                 timeout=WEBHOOK_TIMEOUT_SECONDS)
            result["webhook"] = resp.status_code < 300
            if not result["webhook"]:
                logger.warning("Admin-Alert: Webhook antwortete mit %s", resp.status_code)
        except Exception as e:  # URL nicht loggen (enthaelt oft ein Token)
            result["webhook"] = False
            logger.warning("Admin-Alert: Webhook fehlgeschlagen (%s)", type(e).__name__)
    return result


def _state_key(key: str) -> str:
    """Schluessel in system_state (String(64)): lange Schluessel werden auf einen Hash gekuerzt."""
    full = STATE_PREFIX + key
    if len(full) <= 64:
        return full
    import hashlib
    return STATE_PREFIX + "h:" + hashlib.sha1(key.encode()).hexdigest()[:40]


def _load(key: str) -> dict:
    from app.domain.system.models import SystemState
    state = db.session.get(SystemState, _state_key(key))
    return dict(state.value) if state and isinstance(state.value, dict) else {}


def _store(key: str, value: dict) -> None:
    from sqlalchemy.exc import IntegrityError
    from app.domain.system.models import SystemState
    for _ in range(2):
        state = db.session.get(SystemState, _state_key(key))
        if state is None:
            db.session.add(SystemState(key=_state_key(key), value=value))
        else:
            state.value = value
        try:
            db.session.commit()
            return
        except IntegrityError:
            db.session.rollback()


def raise_alert(key: str, subject: str, message: str, now: datetime | None = None) -> bool:
    """Meldet eine Stoerung, entprellt. True = es wurde versendet."""
    if not any(configured_channels().values()):
        return False
    try:
        now = now or _now()
        cooldown = int(current_app.config.get("ADMIN_ALERT_COOLDOWN_MINUTES", 360))
        value = _load(key)
        last = value.get("last_sent_at")
        if value.get("active") and last:
            age = (now - datetime.fromisoformat(last).replace(tzinfo=None)).total_seconds()
            if age < cooldown * 60:
                return False
        send_admin_alert(subject, message)
        _store(key, {"active": True, "last_sent_at": iso_utc(now)})
        return True
    except Exception:  # pragma: no cover - darf nie stoeren
        db.session.rollback()
        logger.exception("Admin-Alert %s fehlgeschlagen", key)
        return False


def clear_alert(key: str, subject: str, message: str, now: datetime | None = None) -> bool:
    """Meldet Entwarnung (einmalig), falls der Ausloeser zuvor gemeldet war. True = Entwarnung versendet."""
    try:
        value = _load(key)
        if not value.get("active"):
            return False
        _store(key, {"active": False, "last_sent_at": value.get("last_sent_at"), "cleared_at": iso_utc(now or _now())})
        if current_app.config.get("ADMIN_ALERT_RECOVERY", True) and any(configured_channels().values()):
            send_admin_alert(subject, message)
            return True
        return False
    except Exception:  # pragma: no cover
        db.session.rollback()
        logger.exception("Admin-Alert-Entwarnung %s fehlgeschlagen", key)
        return False


def check_alerts(now: datetime | None = None) -> dict:
    """Prueft die Betriebsausloeser und meldet/entwarnt. Rueckgabe: {ausloeser: "alert"|"ok"|"suppressed"}.

    Ausloeser: Billing-Tick ausgefallen (`billing_tick`), Fehler im letzten Tick (`billing_errors`),
    bezahlte Bestellungen warten zu lange (`waiting_orders`). Wird am Ende jedes Ticks und von
    `cli.py alert-check` (z.B. per Cron, unabhaengig vom Tick) aufgerufen.
    """
    from app.domain.billing.service import get_tick_status
    now = now or _now()
    out = {}

    def apply(key, bad, subject, message, ok_message):
        if bad:
            out[key] = "alert" if raise_alert(key, subject, message, now) else "suppressed"
        else:
            clear_alert(key, f"Astra: Entwarnung – {subject.removeprefix('Astra: ')}", ok_message, now)
            out[key] = "ok"

    status = get_tick_status(now)
    since = "noch nie" if status["age_seconds"] is None else f"vor {status['age_seconds'] // 60} Minuten"
    apply("billing_tick", not status["healthy"], "Astra: Billing-Tick läuft nicht",
          f"Der Billing-Tick lief zuletzt {since} (erlaubt: {status['max_age_minutes']} Minuten). "
          f"{status['orders_needing_tick']} Bestellung(en) warten auf ihn: keine Sperren, Erinnerungen oder "
          f"Nachbereitstellungen. Compose-Service 'billing' prüfen.",
          "Der Billing-Tick läuft wieder.")

    errors = (status.get("last_summary") or {}).get("errors") or []
    apply("billing_errors", bool(errors), "Astra: Billing-Tick mit Fehlern",
          f"Der letzte Billing-Tick meldete {len(errors)} Fehler, z.B. {errors[0] if errors else ''}. "
          f"Logs des Service 'billing' prüfen.",
          "Der letzte Billing-Tick lief ohne Fehler.")

    wait = status["awaiting_provisioning"]
    apply("waiting_orders", wait["waiting_too_long"], "Astra: Bezahlte Bestellungen warten auf Platz",
          f"{wait['count']} bezahlte Bestellung(en) warten auf einen freien Node, die älteste seit "
          f"{wait['oldest_wait_hours']} Stunden (Schwelle {wait['warn_after_hours']} Stunden). Kapazität prüfen.",
          "Es warten keine bezahlten Bestellungen mehr zu lange auf einen Node.")
    return out


def alert_payment_problem(order_uuid: str | None, status: str, detail: str | None, event_id: str) -> bool:
    """Meldet ein Zahlungsereignis mit Status mismatch/unapplied (entprellt pro Bestellung und Status)."""
    label = {
        "mismatch": "Zahlung weicht von der Bestellung ab", "unapplied": "Zahlung nicht verbucht",
        "refunded": "Zahlung erstattet", "disputed": "Zahlungsstreit eröffnet",
        "dispute_won": "Zahlungsstreit gewonnen", "dispute_lost": "Zahlungsstreit verloren",
        "dispute_closed": "Zahlungsstreit beendet",
    }.get(status, status)
    return raise_alert(
        f"payment:{order_uuid or event_id}:{status}", f"Astra: {label}",
        f"{detail or ''}\nBestellung: {order_uuid or '-'}\nZahlungsereignis: {event_id}\n"
        f"Details unter GET /api/admin/payment-events"
        + ("; Erstattung im Zahlungsanbieter prüfen." if status in ("mismatch", "unapplied") else "."),
    )
