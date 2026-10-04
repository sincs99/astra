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
