"""Astra Backend – Flask App Factory (M21: Deployment & Operations Readiness).

Erweitert um:
- Strukturiertes Logging
- Startup-Validierung fuer Produktion
- Reverse-Proxy-Unterstuetzung (ProxyFix)
- Security Headers
- Rate Limiting fuer Auth-Endpunkte
- Bootstrap-/Seed-Workflow
- Konsolidierte Ops-Endpunkte (liveness / readiness)
- Base-URL-/Websocket-URL-Builder
"""

import logging
import os
import sys
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from app.config import config_by_name
from app.extensions import db, migrate, jwt, cors
from app.version import VERSION


__version__ = VERSION


# ── Logging-Setup ───────────────────────────────────────


def _setup_logging(app: Flask) -> None:
    """Konfiguriert strukturiertes Logging basierend auf Config."""
    log_level = getattr(logging, app.config.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_format = app.config.get(
        "LOG_FORMAT",
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Root-Logger konfigurieren
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Handler nur setzen wenn keiner da ist (vermeidet Duplikate)
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(handler)

    # Werkzeug-Logger etwas leiser
    logging.getLogger("werkzeug").setLevel(max(log_level, logging.WARNING))


# ── App Factory ─────────────────────────────────────────


def create_app(config_name: str | None = None) -> Flask:
    """Erstellt und konfiguriert die Flask-Anwendung."""

    if config_name is None:
        config_name = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development"))

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Logging als erstes
    _setup_logging(app)
    logger = logging.getLogger("astra.startup")

    logger.info(
        "Astra %s startet – Umgebung: %s, Debug: %s",
        __version__, config_name, app.config.get("DEBUG", False),
    )

    # ── Reverse-Proxy-Unterstuetzung ────────────────────
    if app.config.get("PROXY_FIX_ENABLED"):
        _apply_proxy_fix(app)
        logger.info("ProxyFix aktiviert (X-For=%s, X-Proto=%s)",
                     app.config["PROXY_FIX_X_FOR"], app.config["PROXY_FIX_X_PROTO"])

    # ── Erweiterungen initialisieren ────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # CORS mit konfigurierbaren Origins
    cors_origins = app.config.get("CORS_ORIGINS", "*")
    if cors_origins != "*":
        origins = [o.strip() for o in cors_origins.split(",")]
    else:
        origins = cors_origins
    cors.init_app(app, origins=origins, supports_credentials=True)

    # Modelle importieren, damit Flask-Migrate sie erkennt
    _import_models()

    # Runner initialisieren
    _init_runner(app)

    # Job-System initialisieren (M23)
    _init_jobs(app)

    # Blueprints registrieren
    _register_blueprints(app)

    # Security Headers
    _register_security_headers(app)

    # Rate Limiting (lightweight, ohne externe Abhaengigkeit)
    _register_rate_limiting(app)

    # Ops-Endpunkte registrieren
    _register_ops_endpoints(app)

    # Startup-Validierung
    _validate_startup(app, config_name)

    logger.info("Astra %s bereit - %s", __version__, app.config.get("BASE_URL", ""))

    return app


# ── Reverse Proxy ───────────────────────────────────────


def _apply_proxy_fix(app: Flask) -> None:
    """Wendet Werkzeug ProxyFix an fuer korrekte IP/Proto-Erkennung hinter Proxy."""
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=app.config.get("PROXY_FIX_X_FOR", 1),
        x_proto=app.config.get("PROXY_FIX_X_PROTO", 1),
        x_host=app.config.get("PROXY_FIX_X_HOST", 0),
        x_prefix=app.config.get("PROXY_FIX_X_PREFIX", 0),
    )


# ── Security Headers ───────────────────────────────────


def _register_security_headers(app: Flask) -> None:
    """Registriert After-Request-Hook fuer Security Headers."""

    @app.after_request
    def add_security_headers(response):
        # Nicht im Testing-Modus
        if app.config.get("TESTING"):
            return response

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )

        # Cache-Control fuer API-Responses
        if request.path.startswith("/api/"):
            response.headers.setdefault(
                "Cache-Control", "no-store, no-cache, must-revalidate"
            )

        # Server-Header entfernen
        response.headers.pop("Server", None)

        return response


# ── Rate Limiting ───────────────────────────────────────


_rate_limit_store: dict[str, list] = {}


def _register_rate_limiting(app: Flask) -> None:
    """Einfaches In-Memory Rate Limiting fuer Auth-Endpunkte."""

    @app.before_request
    def check_rate_limit():
        if not app.config.get("RATELIMIT_ENABLED", True):
            return None

        # Nur Auth-Endpunkte limitieren
        auth_paths = ["/api/auth/login"]
        if request.path not in auth_paths:
            return None

        max_per_minute = app.config.get("RATELIMIT_AUTH_PER_MINUTE", 20)
        client_ip = request.remote_addr or "unknown"
        key = f"{client_ip}:{request.path}"
        now = datetime.now(timezone.utc).timestamp()
        window = 60.0  # 1 Minute

        # Alte Eintraege bereinigen
        if key in _rate_limit_store:
            _rate_limit_store[key] = [
                t for t in _rate_limit_store[key] if now - t < window
            ]
        else:
            _rate_limit_store[key] = []

        if len(_rate_limit_store[key]) >= max_per_minute:
            return jsonify({
                "error": "Rate limit exceeded",
                "retry_after": int(window),
            }), 429

        _rate_limit_store[key].append(now)
        return None


# ── Runner-Init ─────────────────────────────────────────


def _init_runner(app: Flask) -> None:
    """Initialisiert den Runner-Adapter basierend auf RUNNER_ADAPTER Config."""
    from app.infrastructure.runner import StubRunnerAdapter, WingsRunnerAdapter
    from app.domain.instances.service import set_runner

    adapter_name = app.config.get("RUNNER_ADAPTER", "stub").lower()
    timeout = (
        app.config.get("RUNNER_TIMEOUT_CONNECT", 5),
        app.config.get("RUNNER_TIMEOUT_READ", 30),
    )
    debug = app.config.get("RUNNER_DEBUG", False)

    if adapter_name == "wings":
        runner = WingsRunnerAdapter(timeout=timeout, debug=debug)
        logging.getLogger("astra.startup").info(
            "Runner-Adapter: Wings (Timeout: %s)", timeout
        )
    else:
        runner = StubRunnerAdapter()
        logging.getLogger("astra.startup").info("Runner-Adapter: Stub")

    set_runner(runner)

    # Runner-Info im App-Context speichern fuer Debug-Endpunkte
    app.config["_RUNNER_ADAPTER_NAME"] = adapter_name


# ── Job-System (M23) ───────────────────────────────────


def _init_jobs(app: Flask) -> None:
    """Initialisiert das Job-/Queue-System."""
    from app.infrastructure.jobs.handlers import setup_handlers
    from app.infrastructure.jobs.queue import set_queue, SyncQueue

    # Handler registrieren
    setup_handlers()

    # Queue-Backend waehlen
    queue_backend = app.config.get("JOB_QUEUE_BACKEND", "sync")
    if queue_backend == "redis":
        from app.infrastructure.jobs.queue import RedisQueue
        redis_url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
        set_queue(RedisQueue(redis_url))
    elif queue_backend == "thread":
        from app.infrastructure.jobs.queue import ThreadQueue
        set_queue(ThreadQueue())
    else:
        set_queue(SyncQueue())

    logging.getLogger("astra.startup").info("Job-Queue: %s", queue_backend)


# ── Modell-Import ───────────────────────────────────────


def _import_models() -> None:
    """Importiert alle Domain-Modelle fuer SQLAlchemy/Migrate."""
    from app.domain.users import models as _users  # noqa: F401
    from app.domain.agents import models as _agents  # noqa: F401
    from app.domain.blueprints import models as _blueprints  # noqa: F401
    from app.domain.instances import models as _instances  # noqa: F401
    from app.domain.endpoints import models as _endpoints  # noqa: F401
    from app.domain.backups import models as _backups  # noqa: F401
    from app.domain.collaborators import models as _collabs  # noqa: F401
    from app.domain.routines import models as _routines  # noqa: F401
    from app.domain.activity import models as _activity  # noqa: F401
    from app.domain.webhooks import models as _webhooks  # noqa: F401
    from app.domain.databases import models as _databases  # noqa: F401
    from app.domain.auth import models as _auth_models  # noqa: F401
    from app.infrastructure.jobs import models as _job_models  # noqa: F401


# ── Blueprint-Registrierung ────────────────────────────


def _register_blueprints(app: Flask) -> None:
    """Registriert alle API-Blueprints."""

    from app.api.admin.routes import admin_bp
    from app.api.client.routes import client_bp
    from app.api.agent.routes import agent_bp
    from app.api.auth.routes import auth_bp

    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(client_bp, url_prefix="/api/client")
    app.register_blueprint(agent_bp, url_prefix="/api/agent")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")


# ── Ops-Endpunkte ──────────────────────────────────────


def _register_ops_endpoints(app: Flask) -> None:
    """Registriert konsolidierte Operations-Endpunkte."""

    @app.route("/health")
    def health_liveness():
        """Liveness-Check: App laeuft und antwortet."""
        return jsonify({
            "status": "ok",
            "service": "astra-backend",
            "version": __version__,
        })

    @app.route("/health/ready")
    def health_readiness():
        """Readiness-Check: App ist bereit, Requests zu verarbeiten.

        Prueft DB-Verbindung und gibt detaillierten Status zurueck.
        """
        checks: dict = {"app": "ok"}
        overall = "ok"

        # DB-Check
        try:
            db.session.execute(db.text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {type(e).__name__}"
            overall = "degraded"

        # Maintenance-Mode
        if app.config.get("MAINTENANCE_MODE"):
            overall = "maintenance"

        status_code = 200 if overall == "ok" else 503
        return jsonify({
            "status": overall,
            "version": __version__,
            "environment": app.config.get("APP_ENV", "unknown"),
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), status_code

    @app.route("/ops/info")
    def ops_info():
        """Nicht-sensitive Betriebsinformationen fuer Ops-Teams."""
        from app.version import RELEASE_PHASE
        return jsonify({
            "service": "astra-backend",
            "version": __version__,
            "release_phase": RELEASE_PHASE,
            "environment": app.config.get("APP_ENV", "unknown"),
            "runner_adapter": app.config.get("_RUNNER_ADAPTER_NAME", "unknown"),
            "proxy_fix": app.config.get("PROXY_FIX_ENABLED", False),
            "maintenance_mode": app.config.get("MAINTENANCE_MODE", False),
            "debug": app.config.get("DEBUG", False),
        })

    @app.route("/ops/version")
    def ops_version():
        """Versions- und Build-Informationen (M24)."""
        from app.version import get_version_info
        info = get_version_info()
        info["service"] = "astra-backend"
        info["environment"] = app.config.get("APP_ENV", "unknown")
        return jsonify(info)

    @app.route("/ops/upgrade-status")
    def ops_upgrade_status():
        """Upgrade-Status: Version, Migration, Kompatibilitaet (M24)."""
        from app.domain.system.upgrade_service import get_upgrade_status
        return jsonify(get_upgrade_status())

    @app.route("/ops/preflight")
    def ops_preflight():
        """Preflight-Check: Konfiguration, DB, Migrationen, Redis (M24)."""
        from app.domain.system.upgrade_service import run_preflight_check
        result = run_preflight_check()
        status_code = 200 if result["compatible"] else 503
        return jsonify(result), status_code


# ── URL-Builder ─────────────────────────────────────────


def build_base_url(app: Flask | None = None) -> str:
    """Gibt die konfigurierte Base URL zurueck.

    Beruecksichtigt Reverse-Proxy-Header falls vorhanden.
    """
    if app is None:
        from flask import current_app
        app = current_app
    return app.config.get("BASE_URL", "http://localhost:5000").rstrip("/")


def build_websocket_url(app: Flask | None = None) -> str:
    """Baut die Websocket-URL basierend auf der Base URL.

    http:// -> ws://, https:// -> wss://
    """
    base = build_base_url(app)
    if base.startswith("https://"):
        return "wss://" + base[8:]
    elif base.startswith("http://"):
        return "ws://" + base[7:]
    return base


# ── Bootstrap / Seed ────────────────────────────────────


def bootstrap_admin(
    username: str = "admin",
    email: str = "admin@astra.local",
    password: str = "admin",
    force: bool = False,
) -> dict:
    """Erstellt den initialen Admin-User falls keiner existiert.

    Returns:
        dict mit 'created' (bool) und 'message'.
    """
    from app.domain.users.models import User

    existing_admin = User.query.filter_by(is_admin=True).first()
    if existing_admin and not force:
        return {
            "created": False,
            "message": f"Admin-User existiert bereits: {existing_admin.username}",
        }

    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing_user:
        if force:
            existing_user.is_admin = True
            db.session.commit()
            return {
                "created": False,
                "message": f"Bestehender User '{existing_user.username}' zum Admin befördert.",
            }
        return {
            "created": False,
            "message": f"User '{username}' existiert bereits.",
        }

    admin = User(
        username=username,
        email=email,
        is_admin=True,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()

    return {
        "created": True,
        "message": f"Admin-User '{username}' erstellt. PASSWORT SOFORT AENDERN!",
    }


# ── Startup-Validierung ────────────────────────────────


def _validate_startup(app: Flask, config_name: str) -> None:
    """Prueft beim Start ob die Konfiguration fuer die Umgebung gueltig ist."""
    logger = logging.getLogger("astra.startup")

    config_cls = config_by_name.get(config_name)
    if config_cls and hasattr(config_cls, "validate_production") and config_name == "production":
        issues = config_cls.validate_production()
        for issue in issues:
            if "KRITISCH" in issue:
                logger.critical(issue)
            else:
                logger.warning(issue)

        critical = [i for i in issues if "KRITISCH" in i]
        if critical:
            logger.critical(
                "Astra startet mit %d kritischen Konfigurationsproblemen! "
                "Bitte beheben fuer sicheren Produktionsbetrieb.",
                len(critical),
            )

    # Log der wichtigsten Config-Werte (KEINE Secrets!)
    logger.info("Database: %s", _mask_db_url(app.config.get("SQLALCHEMY_DATABASE_URI", "")))
    logger.info("CORS Origins: %s", app.config.get("CORS_ORIGINS", "*"))
    logger.info("Rate Limiting: %s", "aktiv" if app.config.get("RATELIMIT_ENABLED") else "deaktiviert")


def _mask_db_url(url: str) -> str:
    """Maskiert Passwort in Datenbank-URL fuer Log-Ausgabe."""
    if "://" in url and "@" in url:
        # postgresql://user:password@host -> postgresql://user:***@host
        prefix, rest = url.split("://", 1)
        if "@" in rest:
            userinfo, hostpart = rest.rsplit("@", 1)
            if ":" in userinfo:
                user, _ = userinfo.split(":", 1)
                return f"{prefix}://{user}:***@{hostpart}"
    return url
