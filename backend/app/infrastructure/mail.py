"""Mail-Versand: SMTP wenn MAIL_SERVER gesetzt ist, sonst nur Logging.

Im Testmodus werden Mails in `outbox` gesammelt statt versendet.
"""

import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

outbox: list[dict] = []


def send_mail(app, to: str, subject: str, body: str) -> bool:
    """Versendet eine Mail. Gibt True zurueck, wenn sie zugestellt/gesammelt wurde."""
    if app.config.get("TESTING"):
        outbox.append({"to": to, "subject": subject, "body": body})
        return True

    server = app.config.get("MAIL_SERVER")
    if not server:
        logger.warning("MAIL_SERVER nicht gesetzt – Mail an %s nicht versendet: %s", to, subject)
        return False

    msg = EmailMessage()
    msg["From"] = app.config.get("MAIL_FROM", "astra@localhost")
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
