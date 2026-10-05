"""Mail-Versand: SMTP wenn MAIL_SERVER gesetzt ist, sonst nur Logging.

Im Testmodus werden Mails in `outbox` gesammelt statt versendet.
"""

import logging
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

logger = logging.getLogger(__name__)

outbox: list[dict] = []


def from_header(app) -> str:
    """Absender: MAIL_FROM_NAME (leer = SITE_NAME) plus Adresse aus MAIL_FROM. Enthaelt MAIL_FROM schon einen Namen
    ("Name <adresse>"), bleibt er unveraendert (M75)."""
    from email.headerregistry import Address
    raw = app.config.get("MAIL_FROM") or "astra@localhost"
    name, addr = parseaddr(raw)
    if name or not addr:
        return raw
    with app.app_context():
        from app.i18n import site_name
        display = " ".join(str(app.config.get("MAIL_FROM_NAME") or "").split()) or site_name()
    user, _, domain = addr.rpartition("@")
    try:
        return str(Address(display_name=display, username=user, domain=domain)) if domain else str(Address(display_name=display, addr_spec=addr))
    except Exception:  # pragma: no cover - ungueltige Adresse: unveraendert lassen
        return raw


def send_mail(app, to: str, subject: str, body: str) -> bool:
    """Versendet eine Mail. Gibt True zurueck, wenn sie zugestellt/gesammelt wurde."""
    if app.config.get("TESTING"):
        outbox.append({"to": to, "subject": subject, "body": body, "from": from_header(app)})
        return True

    server = app.config.get("MAIL_SERVER")
    if not server:
        logger.warning("MAIL_SERVER nicht gesetzt – Mail an %s nicht versendet: %s", to, subject)
        return False

    msg = EmailMessage()
    msg["From"] = from_header(app)
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(server, app.config.get("MAIL_PORT", 587), timeout=10) as smtp:
            if app.config.get("MAIL_USE_TLS", True):
                smtp.starttls()
            username = app.config.get("MAIL_USERNAME")
            if username:
                smtp.login(username, app.config.get("MAIL_PASSWORD", ""))
            smtp.send_message(msg)
        return True
    except Exception as exc:
        logger.error("Mailversand an %s fehlgeschlagen: %s", to, exc)
        return False
