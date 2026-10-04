"""CAPTCHA-Pruefung (M71), anbieterneutral: Cloudflare Turnstile oder hCaptcha.

`CAPTCHA_PROVIDER` = `none` (Standard), `turnstile` oder `hcaptcha`. Das Frontend zeigt das Widget mit dem
oeffentlichen `CAPTCHA_SITE_KEY` und schickt das Ergebnis als `captcha_token`; der Server prueft es bei
Registrierung und Passwort-Reset-Anfrage per siteverify (Timeout 5 Sekunden). Der geheime Schluessel
`CAPTCHA_SECRET` verlaesst den Server nie. Datenschutz: das Widget und die Pruefung laufen ueber den Anbieter.
"""

import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)

VERIFY_URLS = {
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    "hcaptcha": "https://api.hcaptcha.com/siteverify",
}
PROVIDERS = ("none", "turnstile", "hcaptcha")
TIMEOUT_SECONDS = 5


class CaptchaUnavailable(Exception):
    """Der CAPTCHA-Dienst war nicht erreichbar oder antwortete unbrauchbar."""


def provider() -> str:
    return str(current_app.config.get("CAPTCHA_PROVIDER", "none") or "none").strip().lower()


def public_config() -> dict:
    """Fuer GET /api/auth/captcha: Anbieter und oeffentlicher Site-Key (nie das Secret)."""
    name = provider()
    if name not in VERIFY_URLS:
        return {"provider": "none", "site_key": None}
    return {"provider": name, "site_key": current_app.config.get("CAPTCHA_SITE_KEY") or None}


def required() -> bool:
    return provider() in VERIFY_URLS


def verify(token, remote_ip: str | None = None) -> bool:
    """True, wenn der Anbieter das Token bestaetigt. Ohne Token False. Wirft CaptchaUnavailable bei Netzfehlern."""
    if not isinstance(token, str) or not token.strip() or len(token) > 4096:
        return False
    name = provider()
    secret = current_app.config.get("CAPTCHA_SECRET") or ""
    if name not in VERIFY_URLS or not secret:
        logger.error("CAPTCHA aktiviert (%s), aber CAPTCHA_SECRET fehlt", name)
        raise CaptchaUnavailable("CAPTCHA nicht konfiguriert")
    data = {"secret": secret, "response": token.strip()}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        resp = requests.post(VERIFY_URLS[name], data=data, timeout=TIMEOUT_SECONDS)
        if resp.status_code >= 500:
            raise CaptchaUnavailable(f"HTTP {resp.status_code}")
        payload = resp.json()
    except CaptchaUnavailable:
        raise
    except (requests.RequestException, ValueError) as e:
        logger.warning("CAPTCHA-Dienst nicht erreichbar (%s)", type(e).__name__)
        raise CaptchaUnavailable(type(e).__name__)
    return bool(isinstance(payload, dict) and payload.get("success") is True)
