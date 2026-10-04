"""Astra Backend – Konfigurationsmodul (M21).

Saubere Trennung zwischen Development / Testing / Production.
Alle kritischen Betriebsparameter sind ueber Umgebungsvariablen konfigurierbar.
In Produktion wird bei fehlenden Secrets ein Fehler erzeugt.
"""

import os
import warnings
from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str, default: str | None = None) -> str:
    """Gibt den Umgebungsvariablen-Wert zurueck.

    In Produktion wird bei fehlendem Wert (und ohne Default) ein Fehler erzeugt.
    """
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(
            f"Erforderliche Umgebungsvariable '{name}' ist nicht gesetzt. "
            f"Bitte in .env oder Umgebung definieren."
        )
    return value



def _normalize_database_url(url: str) -> str:
    """Erzwingt den psycopg2-Treiber fuer PostgreSQL-URLs.

    Ab SQLAlchemy 2.1 ist der Standardtreiber fuer `postgresql://` psycopg (v3),
    das nicht installiert ist. `postgresql://` und `postgres://` (Heroku-Stil)
    werden deshalb auf `postgresql+psycopg2://` umgeschrieben; explizite Treiber
    (`postgresql+psycopg://`, `postgresql+pg8000://`) bleiben unveraendert.
    """
    if not url:
        return url
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


class Config:
    """Basis-Konfiguration fuer die Flask-App."""

    # ── Umgebung ────────────────────────────────────────
    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development"))

    # ── Secrets ─────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-key")

    # ── Datenbank ───────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///astra.db"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}

    # ── Redis / Cache / Queue ───────────────────────────
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TYPE = os.getenv("CACHE_TYPE", "simple")  # "simple", "redis"
    CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/1"))

    # ── Runner-Konfiguration ────────────────────────────
    RUNNER_ADAPTER = os.getenv("RUNNER_ADAPTER", "stub")  # "stub" oder "wings"
    RUNNER_TIMEOUT_CONNECT = int(os.getenv("RUNNER_TIMEOUT_CONNECT", "5"))
    RUNNER_TIMEOUT_READ = int(os.getenv("RUNNER_TIMEOUT_READ", "30"))
    RUNNER_DEBUG = os.getenv("RUNNER_DEBUG", "false").lower() == "true"

    # ── Webhook-Retry ───────────────────────────────────
    WEBHOOK_MAX_RETRIES = int(os.getenv("WEBHOOK_MAX_RETRIES", "3"))
    WEBHOOK_RETRY_DELAYS = os.getenv("WEBHOOK_RETRY_DELAYS", "5,15,30")
    WEBHOOK_REQUEST_TIMEOUT = int(os.getenv("WEBHOOK_REQUEST_TIMEOUT", "10"))

    # ── Auth / Session / MFA ────────────────────────────
    JWT_ACCESS_TOKEN_EXPIRES_HOURS = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "24"))
    MFA_ISSUER_NAME = os.getenv("MFA_ISSUER_NAME", "Astra")
    MAX_API_KEYS_PER_USER = int(os.getenv("MAX_API_KEYS_PER_USER", "10"))

    # ── CORS / Trusted Hosts / Base URL ─────────────────
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # ── Reverse Proxy ───────────────────────────────────
    TRUSTED_PROXIES = os.getenv("TRUSTED_PROXIES", "127.0.0.1")
    PROXY_FIX_ENABLED = os.getenv("PROXY_FIX_ENABLED", "false").lower() == "true"
    PROXY_FIX_X_FOR = int(os.getenv("PROXY_FIX_X_FOR", "1"))
    PROXY_FIX_X_PROTO = int(os.getenv("PROXY_FIX_X_PROTO", "1"))
    PROXY_FIX_X_HOST = int(os.getenv("PROXY_FIX_X_HOST", "0"))
    PROXY_FIX_X_PREFIX = int(os.getenv("PROXY_FIX_X_PREFIX", "0"))

    # ── Secure Cookies ──────────────────────────────────
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

    # ── Rate Limiting ───────────────────────────────────
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "true").lower() == "true"
    RATELIMIT_AUTH_PER_MINUTE = int(os.getenv("RATELIMIT_AUTH_PER_MINUTE", "20"))

    # ── Admin-Guard (M35) ───────────────────────────────
    # Nur fuer Tests abschaltbar; in Dev/Prod immer aktiv.
    ADMIN_GUARD_ENABLED = True

    # ── Accounts / Mail ─────────────────────────────────
    REGISTRATION_ENABLED = os.getenv("REGISTRATION_ENABLED", "false").lower() == "true"
    # M46: Tage zwischen Ablauf der Laufzeit (Suspend) und automatischer Loeschung der Instance
    BILLING_GRACE_DAYS = max(int(os.getenv("BILLING_GRACE_DAYS", "7")), 0)
    # M53: Warnung, wenn der Billing-Tick laenger als so viele Minuten nicht gelaufen ist (Tick laeuft alle ~5 Minuten)
    BILLING_TICK_MAX_AGE_MINUTES = max(int(os.getenv("BILLING_TICK_MAX_AGE_MINUTES", "15")), 1)
    BILLING_WAIT_WARN_HOURS = max(int(os.getenv("BILLING_WAIT_WARN_HOURS", "24")), 1)
    # M58: aktive Admin-Benachrichtigung (leer = aus); Entprellung in Minuten, Entwarnung einmalig
    ADMIN_ALERT_EMAIL = os.getenv("ADMIN_ALERT_EMAIL", "").strip()
    ADMIN_ALERT_WEBHOOK_URL = os.getenv("ADMIN_ALERT_WEBHOOK_URL", "").strip()
    ADMIN_ALERT_COOLDOWN_MINUTES = max(int(os.getenv("ADMIN_ALERT_COOLDOWN_MINUTES", "360")), 1)
    ADMIN_ALERT_RECOVERY = os.getenv("ADMIN_ALERT_RECOVERY", "true").lower() == "true"
    # M62: Belege (Grundlage, kein Steuerbeleg): Nummernformat mit {year} und {seq}, Anbietertext und Fusszeile
    INVOICE_NUMBER_FORMAT = (os.getenv("INVOICE_NUMBER_FORMAT") or "AST-{year}-{seq:05d}").strip()
    INVOICE_SELLER = os.getenv("INVOICE_SELLER", "").replace("\\n", "\n").strip()
    RECEIPT_FOOTER = os.getenv("RECEIPT_FOOTER", "").replace("\\n", "\n").strip()
    # M46: Erinnerungsmail so viele Tage vor Laufzeitende (0 = keine Erinnerung)
    BILLING_REMINDER_DAYS = max(int(os.getenv("BILLING_REMINDER_DAYS", "3")), 0)
    # M48: Zahlungsanbieter: "manual" (Admin bestaetigt Zahlungen) oder "stripe" (Checkout + Webhook)
    PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "manual").strip().lower()
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    # M38: Login erst nach bestaetigter E-Mail-Adresse (Registrierung sendet Verifizierungs-Link)
    EMAIL_VERIFICATION_REQUIRED = os.getenv("EMAIL_VERIFICATION_REQUIRED", "false").lower() == "true"
    EMAIL_VERIFICATION_TTL_HOURS = int(os.getenv("EMAIL_VERIFICATION_TTL_HOURS", "48"))
    PASSWORD_RESET_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "60"))
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "astra@localhost")

    # ── Logging ─────────────────────────────────────────
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # ── Betrieb ─────────────────────────────────────────
    MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"

    @classmethod
    def is_production(cls) -> bool:
        """Prueft ob die Konfiguration fuer Produktion bestimmt ist."""
        return cls.APP_ENV == "production"

    @classmethod
    def validate_production(cls) -> list[str]:
        """Prueft ob alle fuer Produktion kritischen Werte gesetzt sind.

        Gibt eine Liste von Warnungen/Fehlern zurueck.
        """
        issues: list[str] = []
        insecure_defaults = {
            "SECRET_KEY": "dev-secret-key",
            "JWT_SECRET_KEY": "dev-jwt-secret-key",
        }
        for key, insecure in insecure_defaults.items():
            val = getattr(cls, key, None)
            if val == insecure:
                issues.append(
                    f"KRITISCH: {key} verwendet den unsicheren Default-Wert. "
                    f"Bitte einen sicheren Wert setzen!"
                )

        if cls.PAYMENT_PROVIDER not in ("manual", "stripe"):
            issues.append(
                f"KRITISCH: PAYMENT_PROVIDER '{cls.PAYMENT_PROVIDER}' ist unbekannt (erlaubt: manual, stripe)."
            )
        if cls.PAYMENT_PROVIDER == "stripe" and not (cls.STRIPE_SECRET_KEY and cls.STRIPE_WEBHOOK_SECRET):
            issues.append(
                "KRITISCH: PAYMENT_PROVIDER=stripe, aber STRIPE_SECRET_KEY und/oder STRIPE_WEBHOOK_SECRET fehlen."
            )

        from app.domain.billing.receipts import validate_number_format
        problem = validate_number_format(cls.INVOICE_NUMBER_FORMAT)
        if problem:
            issues.append(f"KRITISCH: INVOICE_NUMBER_FORMAT ist ungueltig: {problem}")

        if cls.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
            issues.append(
                "WARNUNG: SQLite ist fuer Produktion nicht empfohlen. "
                "Bitte DATABASE_URL auf PostgreSQL setzen."
            )

        if cls.CORS_ORIGINS == "*":
            issues.append(
                "WARNUNG: CORS_ORIGINS ist auf '*' gesetzt. "
                "In Produktion auf konkrete Origins einschraenken."
            )

        if not cls.SESSION_COOKIE_SECURE:
            issues.append(
                "WARNUNG: SESSION_COOKIE_SECURE ist deaktiviert. "
                "Fuer HTTPS-Betrieb aktivieren."
            )

        return issues


class DevelopmentConfig(Config):
    """Entwicklungs-Konfiguration."""

    APP_ENV = "development"
    DEBUG = True
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")


class ProductionConfig(Config):
    """Produktions-Konfiguration mit strengen Defaults."""

    APP_ENV = "production"
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING")

    # In Prod: ProxyFix standardmaessig aktiv
    PROXY_FIX_ENABLED = os.getenv("PROXY_FIX_ENABLED", "true").lower() == "true"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")


class TestingConfig(Config):
    """Test-Konfiguration mit In-Memory-SQLite."""

    APP_ENV = "testing"
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "testing-secret-key"
    JWT_SECRET_KEY = "testing-jwt-secret-key"
    RATELIMIT_ENABLED = False
    ADMIN_GUARD_ENABLED = False  # Legacy-Tests rufen /api/admin ohne Auth auf; test_m35 schaltet ihn ein
    WEBHOOK_MAX_RETRIES = 1
    WEBHOOK_RETRY_DELAYS = "0"
    WEBHOOK_REQUEST_TIMEOUT = 2


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
