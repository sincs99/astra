"""Sprache fuer Servertexte (Mails, Belege): Kunden-Locale, Fallback Deutsch (M67)."""

SUPPORTED_LOCALES = ("de", "en")
DEFAULT_LOCALE = "de"


def normalize_locale(value) -> str:
    """Gueltige Locale oder der Standard. Akzeptiert auch "en-US"/"EN" (-> "en")."""
    code = str(value or "").strip().lower().replace("_", "-").split("-")[0]
    return code if code in SUPPORTED_LOCALES else DEFAULT_LOCALE


def validate_locale(value) -> str | None:
    """Gibt die Locale zurueck, wenn sie exakt unterstuetzt ist ("de"/"en"), sonst None."""
    return value if isinstance(value, str) and value in SUPPORTED_LOCALES else None


class _KeepMissing(dict):
    """Fehlende Platzhalter bleiben als {name} stehen, statt eine Mail scheitern zu lassen."""

    def __missing__(self, key):
        return "{" + key + "}"


def tr(locale, key: str, **fmt) -> str:
    """Text zum Schluessel in der Sprache des Kunden; unbekannte Sprache oder fehlender Eintrag: Deutsch,
    fehlt auch dort: der Schluessel selbst."""
    from app.i18n.messages import MESSAGES
    text = MESSAGES.get(normalize_locale(locale), {}).get(key)
    if text is None:
        text = MESSAGES[DEFAULT_LOCALE].get(key, key)
    return text.format_map(_KeepMissing(fmt))


_EN_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_EN_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}


def format_money(locale, cents: int, currency: str) -> str:
    """DE: "1.234,56 EUR", EN: "€1,234.56" (bekannte Symbole, sonst "GBP 1,234.56"). CHF (M74): DE "CHF 1'234.56"
    (Hochkomma, Punkt, Waehrung vorn), EN "CHF 1,234.56"."""
    if currency == "CHF" and normalize_locale(locale) == "de":
        sign = "-" if cents < 0 else ""
        return f"{sign}CHF " + f"{abs(cents) / 100:,.2f}".replace(",", "'")
    if normalize_locale(locale) == "en":
        amount = f"{abs(cents) / 100:,.2f}"
        sign = "-" if cents < 0 else ""
        symbol = _EN_SYMBOLS.get(currency)
        return f"{sign}{symbol}{amount}" if symbol else f"{sign}{currency} {amount}"
    return f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" {currency}"


def format_date(locale, dt) -> str:
    """DE: "04.10.2026", EN: "4 Oct 2026" (ohne Locale-Abhaengigkeit des Servers)."""
    if normalize_locale(locale) == "en":
        return f"{dt.day} {_EN_MONTHS[dt.month - 1]} {dt.year}"
    return dt.strftime("%d.%m.%Y")


def format_datetime(locale, dt) -> str:
    """DE: "04.10.2026 14:05 UTC", EN: "4 Oct 2026, 14:05 UTC"."""
    if normalize_locale(locale) == "en":
        return f"{format_date('en', dt)}, {dt:%H:%M} UTC"
    return f"{dt:%d.%m.%Y %H:%M} UTC"


def request_locale() -> str:
    """Sprache des aktuellen Requests (M72): angemeldeter Nutzer -> users.locale (nicht gesetzt = Deutsch); sonst der erste
    passende Eintrag von Accept-Language (de/en, nach q-Wert); sonst Deutsch. Das Ergebnis gilt je Request."""
    from flask import g, has_request_context, request
    if not has_request_context():
        return DEFAULT_LOCALE
    cached = g.get("_request_locale")
    if cached:
        return cached
    locale = None
    try:
        from app.domain.auth.service import get_current_user
        user = get_current_user()
        if user is not None:
            locale = normalize_locale(user.locale)
    except Exception:  # Sprachwahl darf nie an der Anmeldepruefung scheitern
        locale = None
    if locale is None:
        try:
            locale = request.accept_languages.best_match(list(SUPPORTED_LOCALES)) or DEFAULT_LOCALE
        except Exception:
            locale = DEFAULT_LOCALE
    g._request_locale = locale
    return locale
