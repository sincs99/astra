"""Admin-API-Routen (inkl. M22 Fleet Monitoring)."""

import ipaddress
from datetime import datetime, timezone
from flask import Blueprint, current_app, jsonify, request
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.blueprints.models import Blueprint as BlueprintModel
from app.domain.users.models import User
from app.domain.instances.models import Instance
from app.domain.endpoints.models import Endpoint
from app.domain.instances.service import (
    create_instance, InstanceCreationError,
    transfer_instance, InstanceActionError,
    suspend_instance, unsuspend_instance,
)
from app.utils.timeutil import iso_utc

admin_bp = Blueprint("admin", __name__)

# Pfade ohne Admin-Pflicht (Liveness-Check)
_PUBLIC_ADMIN_ENDPOINTS = {"admin.health"}


@admin_bp.before_request
def _admin_guard():
    """Erzwingt Admin-Authentifizierung fuer den gesamten Admin-Blueprint (M35)."""
    if not current_app.config.get("ADMIN_GUARD_ENABLED", True):
        return None
    if request.method == "OPTIONS" or request.endpoint in _PUBLIC_ADMIN_ENDPOINTS:
        return None
    from app.domain.auth.service import require_admin
    _, err = require_admin()
    return err

# Wings-Verbindungsfelder, die ueber POST/PATCH /agents gepflegt werden duerfen (M33)
_AGENT_CONNECTION_FIELDS = (
    "scheme", "behind_proxy", "daemon_connect", "daemon_listen",
    "daemon_sftp", "daemon_base", "upload_size",
)
_AGENT_CAPACITY_FIELDS = (
    "memory_total", "disk_total", "cpu_total",
    "memory_overalloc", "disk_overalloc", "cpu_overalloc",
)


def _require_admin_user():
    """Gibt (user, None) oder (None, error_response) zurueck.

    Schutz fuer Endpunkte, die Node-Secrets ausliefern oder aendern (M33).
    Nutzt den zentralen Auth-Service (JWT, API-Key, Dev/Test-Fallback X-User-Id).
    """
    from app.domain.auth.service import require_admin

    return require_admin()


def _apply_agent_connection_fields(agent: Agent, data: dict) -> str | None:
    """Uebernimmt Wings-Verbindungsfelder aus dem Request. Gibt Fehlertext oder None zurueck."""
    if "scheme" in data:
        scheme = str(data["scheme"] or "").lower()
        if scheme not in ("http", "https"):
            return "Field 'scheme' must be 'http' or 'https'"
        agent.scheme = scheme
    if "behind_proxy" in data:
        agent.behind_proxy = bool(data["behind_proxy"])
    for field in ("daemon_connect", "daemon_listen", "daemon_sftp"):
        if field in data:
            try:
                port = int(data[field])
            except (TypeError, ValueError):
                return f"Field '{field}' must be an integer"
            if not 1 <= port <= 65535:
                return f"Field '{field}' must be between 1 and 65535"
            setattr(agent, field, port)
    if "upload_size" in data:
        try:
            size = int(data["upload_size"])
        except (TypeError, ValueError):
            return "Field 'upload_size' must be an integer"
        if size < 1:
            return "Field 'upload_size' must be positive"
        agent.upload_size = size
    if "daemon_base" in data:
        base = str(data["daemon_base"] or "").strip()
        if not base.startswith("/"):
            return "Field 'daemon_base' must be an absolute path"
        agent.daemon_base = base
    # Kapazitaet (M22) und Ueberallokation – Ganzzahlen >= 0, 0 = kein Limit
    for field in _AGENT_CAPACITY_FIELDS:
        if field in data:
            value = data[field]
            if isinstance(value, bool) or not isinstance(value, int):
                try:
                    value = int(str(value))
                except (TypeError, ValueError):
                    return f"Field '{field}' must be an integer"
            if value < 0:
                return f"Field '{field}' must be >= 0"
            if field.endswith("_overalloc") and value > 1000:
                return f"Field '{field}' must be <= 1000"
            setattr(agent, field, value)
    return None


# ── Health ──────────────────────────────────────────────


@admin_bp.route("/health")
def health():
    return jsonify({"status": "ok", "scope": "admin"})


@admin_bp.route("/health/detailed", methods=["GET"])
def health_detailed():
    """Detaillierter Health-Check: App, DB, Agents."""
    checks = {"app": "ok"}

    # DB-Check
    try:
        db.session.execute(db.text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Agent-Uebersicht
    try:
        agents = Agent.query.all()
        total = len(agents)
        active = sum(1 for a in agents if a.is_active)
        stale = sum(1 for a in agents if a.is_active and a.is_stale())
        checks["agents"] = {
            "total": total,
            "active": active,
            "stale": stale,
        }
    except Exception as e:
        checks["agents"] = f"error: {str(e)}"

    overall = "ok" if checks["database"] == "ok" else "degraded"
    return jsonify({"status": overall, "checks": checks})


@admin_bp.route("/agents/health", methods=["GET"])
def agents_health():
    """Health-Status aller Agents."""
    agents = Agent.query.order_by(Agent.name).all()
    result = []
    for a in agents:
        result.append({
            "id": a.id,
            "name": a.name,
            "fqdn": a.fqdn,
            "is_active": a.is_active,
            "last_seen_at": iso_utc(a.last_seen_at),
            "is_stale": a.is_stale(),
            "instances_count": len(a.instances) if hasattr(a, "instances") else 0,
        })
    return jsonify(result)


# ── Users ───────────────────────────────────────────────


@admin_bp.route("/users", methods=["GET"])
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users])


@admin_bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email:
        return jsonify({"error": "Fields 'username' and 'email' are required"}), 400

    if not password:
        return jsonify({"error": "Field 'password' is required"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": f"Username '{username}' already exists"}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({"error": f"Email '{email}' already exists"}), 409

    user = User(
        username=username,
        email=email,
        is_admin=data.get("is_admin", False),
        email_verified_at=datetime.now(timezone.utc),  # vom Admin angelegt = bestaetigt
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify(user.to_dict()), 201


# ── Agents ──────────────────────────────────────────────


@admin_bp.route("/agents", methods=["GET"])
def list_agents():
    agents = Agent.query.order_by(Agent.created_at.desc()).all()
    return jsonify([a.to_dict() for a in agents])


@admin_bp.route("/agents", methods=["POST"])
def create_agent():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = data.get("name")
    fqdn = data.get("fqdn")

    if not name or not fqdn:
        return jsonify({"error": "Fields 'name' and 'fqdn' are required"}), 400

    if Agent.query.filter_by(fqdn=fqdn).first():
        return jsonify({"error": f"Agent with fqdn '{fqdn}' already exists"}), 409

    agent = Agent(name=name, fqdn=fqdn)
    # M33: Node-Credentials fuer die Wings Remote-API
    agent.generate_daemon_credentials()
    err = _apply_agent_connection_fields(agent, data)
    if err:
        return jsonify({"error": err}), 400

    db.session.add(agent)
    db.session.commit()

    return jsonify(agent.to_dict()), 201


@admin_bp.route("/agents/<int:agent_id>", methods=["PATCH"])
def update_agent(agent_id: int):
    """Aktualisiert Name, FQDN, Aktiv-Flag und Wings-Verbindungsfelder eines Agents (M33)."""
    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify({"error": f"Agent mit ID {agent_id} nicht gefunden"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    if "name" in data:
        if not data["name"]:
            return jsonify({"error": "Field 'name' must not be empty"}), 400
        agent.name = data["name"]
    if "fqdn" in data:
        fqdn = data["fqdn"]
        if not fqdn:
            return jsonify({"error": "Field 'fqdn' must not be empty"}), 400
        other = Agent.query.filter(Agent.fqdn == fqdn, Agent.id != agent.id).first()
        if other:
            return jsonify({"error": f"Agent with fqdn '{fqdn}' already exists"}), 409
        agent.fqdn = fqdn
    if "is_active" in data:
        agent.is_active = bool(data["is_active"])

    err = _apply_agent_connection_fields(agent, data)
    if err:
        return jsonify({"error": err}), 400

    db.session.commit()
    return jsonify(agent.to_dict())


@admin_bp.route("/agents/<int:agent_id>/configuration", methods=["GET"])
def agent_configuration(agent_id: int):
    """Liefert die Wings config.yml fuer einen Agent (M33).

    Enthaelt das Node-Secret – nur fuer Admins.
    Antwort: {"agent_id", "yaml", "config"}
    """
    _, err = _require_admin_user()
    if err:
        return err

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify({"error": f"Agent mit ID {agent_id} nicht gefunden"}), 404

    if not agent.has_daemon_credentials:
        # Agents aus der Zeit vor M33 haben noch keine Credentials
        agent.generate_daemon_credentials()
        db.session.commit()
    if not agent.uuid:
        import uuid as _uuid
        agent.uuid = str(_uuid.uuid4())
        db.session.commit()

    from flask import current_app
    remote_url = current_app.config.get("BASE_URL", "http://localhost:5000")

    return jsonify({
        "agent_id": agent.id,
        "yaml": agent.get_wings_configuration_yaml(remote_url),
        "config": agent.get_wings_configuration(remote_url),
    })


@admin_bp.route("/agents/<int:agent_id>/rotate-credentials", methods=["POST"])
def rotate_agent_credentials(agent_id: int):
    """Erzeugt neue Node-Credentials (token_id + token). Danach config.yml neu ausrollen (M33)."""
    user, err = _require_admin_user()
    if err:
        return err

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify({"error": f"Agent mit ID {agent_id} nicht gefunden"}), 404

    agent.generate_daemon_credentials()
    db.session.commit()

    from app.domain.activity.service import log_event
    try:
        log_event(
            "agent:credentials_rotated",
            actor_id=user.id,
            subject_id=agent.id,
            subject_type="agent",
            description=f"Node-Credentials fuer Agent '{agent.name}' neu erzeugt",
        )
    except Exception:  # pragma: no cover - best-effort
        pass

    return jsonify({
        "message": "Credentials neu erzeugt. config.yml auf dem Node aktualisieren und Wings neu starten.",
        "agent": agent.to_dict(),
    })


# ── Blueprints ──────────────────────────────────────────


def _validate_blueprint_process_fields(data: dict) -> str | None:
    """Validiert die Wings-Prozessfelder eines Blueprints (M33). Gibt Fehlertext oder None zurueck."""
    if "config_startup" in data and data["config_startup"] is not None:
        cfg = data["config_startup"]
        if not isinstance(cfg, dict):
            return "Field 'config_startup' must be an object like {\"done\": [\"...\"]}"
        done = cfg.get("done")
        if done is not None and not isinstance(done, (str, list)):
            return "Field 'config_startup.done' must be a string or a list of strings"
        if isinstance(done, list) and not all(isinstance(d, str) for d in done):
            return "Field 'config_startup.done' must contain only strings"
    if "config_stop" in data and data["config_stop"] is not None:
        if not isinstance(data["config_stop"], str) or len(data["config_stop"]) > 64:
            return "Field 'config_stop' must be a string (max 64 chars)"
    if "config_files" in data and data["config_files"] is not None:
        if not isinstance(data["config_files"], dict):
            return "Field 'config_files' must be an object keyed by file name"
    if "file_denylist" in data and data["file_denylist"] is not None:
        fdl = data["file_denylist"]
        if not isinstance(fdl, list) or not all(isinstance(f, str) for f in fdl):
            return "Field 'file_denylist' must be a list of strings"
    for field in ("install_container", "install_entrypoint"):
        if field in data and data[field] is not None and not isinstance(data[field], str):
            return f"Field '{field}' must be a string"
    return None


@admin_bp.route("/blueprints", methods=["GET"])
def list_blueprints():
    blueprints = BlueprintModel.query.order_by(BlueprintModel.created_at.desc()).all()
    return jsonify([b.to_dict() for b in blueprints])


@admin_bp.route("/blueprints", methods=["POST"])
def create_blueprint():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = data.get("name")
    if not name:
        return jsonify({"error": "Field 'name' is required"}), 400

    err = _validate_blueprint_process_fields(data)
    if err:
        return jsonify({"error": err}), 400

    blueprint = BlueprintModel(
        name=name,
        description=data.get("description"),
        docker_image=data.get("docker_image"),
        startup_command=data.get("startup_command"),
        install_script=data.get("install_script"),
        install_container=data.get("install_container"),
        install_entrypoint=data.get("install_entrypoint"),
        variables=data.get("variables", []),
        config_schema=data.get("config_schema"),
        config_startup=data.get("config_startup"),
        config_stop=data.get("config_stop"),
        config_files=data.get("config_files"),
        file_denylist=data.get("file_denylist"),
    )
    db.session.add(blueprint)
    db.session.commit()

    return jsonify(blueprint.to_dict()), 201


@admin_bp.route("/blueprints/import", methods=["POST"])
def import_blueprint_endpoint():
    """Importiert ein Pterodactyl/Pelican-Egg oder natives Blueprint-JSON ("format": "astra")."""
    from app.domain.blueprints.egg_import import EggImportError, import_blueprint

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "JSON body required"}), 400
    try:
        blueprint = import_blueprint(data)
    except EggImportError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(blueprint.to_dict()), 201


@admin_bp.route("/blueprints/<int:blueprint_id>", methods=["PATCH"])
def update_blueprint(blueprint_id: int):
    blueprint = db.session.get(BlueprintModel, blueprint_id)
    if not blueprint:
        return jsonify({"error": f"Blueprint {blueprint_id} nicht gefunden"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    err = _validate_blueprint_process_fields(data)
    if err:
        return jsonify({"error": err}), 400

    updatable = [
        "name", "description", "docker_image", "startup_command", "install_script",
        "install_container", "install_entrypoint", "variables", "config_schema",
        "config_startup", "config_stop", "config_files", "file_denylist",
    ]
    for field in updatable:
        if field in data:
            setattr(blueprint, field, data[field])

    db.session.commit()
    return jsonify(blueprint.to_dict())


@admin_bp.route("/blueprints/<int:blueprint_id>", methods=["DELETE"])
def delete_blueprint(blueprint_id: int):
    blueprint = db.session.get(BlueprintModel, blueprint_id)
    if not blueprint:
        return jsonify({"error": f"Blueprint {blueprint_id} nicht gefunden"}), 404

    if blueprint.instances:
        return jsonify({"error": "Blueprint wird noch von Instances verwendet"}), 409

    from app.domain.billing.models import Product
    if Product.query.filter_by(blueprint_id=blueprint.id).first():
        return jsonify({"error": "Blueprint wird noch von Produkten verwendet"}), 409

    db.session.delete(blueprint)
    db.session.commit()
    return jsonify({"message": f"Blueprint '{blueprint.name}' gelöscht"})


# ── Produkte und Bestellungen (M44) ─────────────────────


def _billing_error(e):
    body = {"error": e.message}
    if getattr(e, "code", None):
        body["code"] = e.code
    body.update(getattr(e, "extra", None) or {})
    return jsonify(body), e.status_code


@admin_bp.route("/products", methods=["GET"])
def list_products():
    from app.domain.billing.models import Product
    from sqlalchemy.orm import joinedload
    products = Product.query.options(joinedload(Product.blueprint)).order_by(Product.price_cents, Product.id).all()
    return jsonify([p.to_dict() for p in products])


@admin_bp.route("/products", methods=["POST"])
def create_product_route():
    from app.domain.billing.service import BillingError, create_product
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body is required"}), 400
    try:
        return jsonify(create_product(data).to_dict()), 201
    except BillingError as e:
        return _billing_error(e)


@admin_bp.route("/products/<int:product_id>", methods=["GET"])
def get_product_route(product_id: int):
    from app.domain.billing.models import Product
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Produkt nicht gefunden"}), 404
    return jsonify(product.to_dict())


@admin_bp.route("/products/<int:product_id>", methods=["PATCH"])
def update_product_route(product_id: int):
    from app.domain.billing.models import Product
    from app.domain.billing.service import BillingError, update_product
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Produkt nicht gefunden"}), 404
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body is required"}), 400
    try:
        return jsonify(update_product(product, data).to_dict())
    except BillingError as e:
        return _billing_error(e)


@admin_bp.route("/products/<int:product_id>", methods=["DELETE"])
def delete_product_route(product_id: int):
    from app.domain.billing.models import Product
    from app.domain.billing.service import BillingError, delete_product
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Produkt nicht gefunden"}), 404
    try:
        delete_product(product)
    except BillingError as e:
        return _billing_error(e)
    return jsonify({"message": "Produkt geloescht"})


@admin_bp.route("/orders", methods=["GET"])
def list_orders():
    """Alle Bestellungen, optional gefiltert: ?status=...&user_id=...&q=...

    `q` (M65, max. 100 Zeichen, sonst 400) sucht ohne Beachtung der Gross-/Kleinschreibung im
    Verwendungszweck (`payment_purpose`, auch als Praefix wie "ASTRA-0042"), im Servernamen, im
    Nutzernamen und als UUID-Praefix, damit der Admin einen Zahlungseingang direkt zuordnen kann.
    """
    from sqlalchemy.orm import joinedload
    from app.domain.billing.models import Order, ALL_ORDER_STATUSES
    q = (request.args.get("q") or "").strip()
    if len(q) > 100:
        return jsonify({"error": "q darf hoechstens 100 Zeichen lang sein"}), 400
    query = Order.query.options(
        joinedload(Order.user), joinedload(Order.instance).joinedload(Instance.agent),
        joinedload(Order.instance).joinedload(Instance.primary_endpoint),
    )
    status = request.args.get("status")
    if status:
        if status not in ALL_ORDER_STATUSES:
            return jsonify({"error": f"Unbekannter Status '{status}'"}), 400
        query = query.filter(Order.status == status)
    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        query = query.filter(Order.user_id == user_id)
    orders = query.order_by(Order.created_at.desc(), Order.id.desc()).all()
    if q:
        orders = [o for o in orders if _order_matches(o, q.lower())]
    return jsonify([o.to_dict(include_user=True) for o in orders])


def _order_matches(order, needle: str) -> bool:
    """Suchtreffer fuer ?q= (M65): Verwendungszweck/UUID als Praefix, Server- und Nutzername als Teiltext."""
    purpose = (order.payment_purpose or "").lower()
    username = (order.user.username if order.user else "").lower()
    return (purpose.startswith(needle) or order.uuid.lower().startswith(needle)
            or needle in (order.instance_name or "").lower() or needle in username)


@admin_bp.route("/billing/status", methods=["GET"])
def billing_status():
    """Betriebszustand des Billing-Ticks (M53): letzter Lauf, Alter, Ergebnis, Bestellungen je Status.

    `healthy` ist false, wenn Bestellungen auf den Tick warten (aktiv, ueberfaellig, wartend) und der letzte
    Lauf laenger als BILLING_TICK_MAX_AGE_MINUTES zurueckliegt oder fehlt.
    """
    from app.domain.billing.service import get_tick_status
    return jsonify(get_tick_status())


@admin_bp.route("/stats/revenue", methods=["GET"])
def revenue_stats_route():
    """Umsatz der letzten ?days=30 Tage (1 bis 365) auf Basis der Zahlungsbelege (M62), je Waehrung getrennt.

    Antwort: {days, since, by_currency: {"EUR": cents}, paid_count (Erstzahlungen), renewals_count,
    refunded_cents_by_currency, prev_since, prev_by_currency, prev_paid_count, prev_renewals_count}.
    Erstattungen werden getrennt ausgewiesen, nicht abgezogen; prev_* ist der gleich lange Vorzeitraum (M66).
    """
    from app.domain.billing.service import revenue_stats
    raw = request.args.get("days", "30")
    try:
        days = int(raw)
    except ValueError:
        return jsonify({"error": "days muss eine ganze Zahl sein"}), 400
    if not 1 <= days <= 365:
        return jsonify({"error": "days muss zwischen 1 und 365 liegen"}), 400
    return jsonify(revenue_stats(days))


_INVOICE_CSV_COLUMNS = ("number", "kind", "issued_at", "order_uuid", "username", "net_cents", "vat_cents", "vat_rate",
                        "gross_cents", "currency", "payment_reference", "references_number")
_INVOICE_CSV_TEXT = {"number", "kind", "order_uuid", "username", "currency", "payment_reference", "references_number"}


def _csv_text(value) -> str:
    """Textzelle fuer CSV: Formeln (=, +, -, @) werden entschaerft (CSV-Injection ueber Benutzernamen u.a.)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _decimal_de(cents) -> str:
    if cents is None:
        return ""
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100},{abs(cents) % 100:02d}"


@admin_bp.route("/invoices", methods=["GET"])
def list_invoices():
    """Rechnungen und Gutschriften (M70) fuer die Buchhaltung: ?from=YYYY-MM-DD&to=YYYY-MM-DD&format=json|csv.

    Standard: der laufende Monat (UTC) als JSON. `from` und `to` gelten einschliesslich, hoechstens 366 Tage.
    JSON: Liste mit number, kind, issued_at, order_uuid, username, net_cents, vat_cents, vat_rate, gross_cents, currency,
    payment_reference, references_number (Gutschrift -> Nummer der Rechnung); bei Dokumenten vor M70 sind net_cents, vat_cents
    und vat_rate null. CSV: Semikolon, UTF-8 mit BOM, dieselben Spalten plus net, vat, gross als Dezimalzahl mit Komma,
    Dateiname rechnungen-JJJJ-MM.csv. Fehler: 400 `invalid_date`, `invalid_range`, `range_too_large`, `invalid_format`.
    """
    import calendar
    import csv
    import io
    from datetime import date, datetime, timezone
    from flask import Response
    from app.domain.billing.service import list_invoice_documents

    fmt = request.args.get("format", "json").lower()
    if fmt not in ("json", "csv"):
        return jsonify({"error": "format muss json oder csv sein", "code": "invalid_format"}), 400
    today = datetime.now(timezone.utc).date()
    try:
        start = date.fromisoformat(request.args["from"]) if request.args.get("from") else today.replace(day=1)
        end = (date.fromisoformat(request.args["to"]) if request.args.get("to")
               else date(start.year, start.month, calendar.monthrange(start.year, start.month)[1]))
    except ValueError:
        return jsonify({"error": "from und to müssen Datumsangaben im Format JJJJ-MM-TT sein", "code": "invalid_date"}), 400
    if start > end:
        return jsonify({"error": "from darf nicht nach to liegen", "code": "invalid_range"}), 400
    if (end - start).days > 366:
        return jsonify({"error": "Der Zeitraum darf höchstens 366 Tage umfassen", "code": "range_too_large"}), 400

    docs = list_invoice_documents(start, end)
    if fmt == "json":
        return jsonify(docs)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow(list(_INVOICE_CSV_COLUMNS) + ["net", "vat", "gross"])
    for d in docs:
        row = [_csv_text(d[c]) if c in _INVOICE_CSV_TEXT else ("" if d[c] is None else d[c]) for c in _INVOICE_CSV_COLUMNS]
        writer.writerow(row + [_decimal_de(d["net_cents"]), _decimal_de(d["vat_cents"]), _decimal_de(d["gross_cents"])])
    name = (f"rechnungen-{start:%Y-%m}.csv" if (start.year, start.month) == (end.year, end.month)
            else f"rechnungen-{start.isoformat()}_{end.isoformat()}.csv")
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-store"})


@admin_bp.route("/payment-events", methods=["GET"])
def list_payment_events():
    """Zahlungsereignisse des Anbieters (nur lesen), neueste zuerst.

    Filter: ?status=processed|ignored|unapplied|mismatch|received, ?order_uuid=..., ?limit=1..500 (Standard 100).
    `mismatch` (Betrag/Waehrung weicht ab) und `unapplied` (Zahlung fuer beendete Bestellung) brauchen
    Aufmerksamkeit: Erstattung im Zahlungsanbieter pruefen. `received` heisst: Verarbeitung abgebrochen,
    der Anbieter wiederholt die Zustellung.
    """
    from app.domain.billing.models import PaymentEvent
    query = PaymentEvent.query
    status = request.args.get("status")
    if status:
        if status not in ("processed", "ignored", "unapplied", "mismatch", "received"):
            return jsonify({"error": f"Unbekannter Status '{status}'"}), 400
        query = query.filter(PaymentEvent.status == status)
    order_uuid = request.args.get("order_uuid")
    if order_uuid:
        query = query.filter(PaymentEvent.order_uuid == order_uuid)
    raw_limit = request.args.get("limit", "100")
    try:
        limit = int(raw_limit)
    except ValueError:
        limit = 0
    if not 1 <= limit <= 500:
        return jsonify({"error": "Parameter 'limit' muss eine Zahl zwischen 1 und 500 sein"}), 400
    events = query.order_by(PaymentEvent.received_at.desc(), PaymentEvent.id.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in events])


@admin_bp.route("/orders/<string:uuid>", methods=["GET"])
def get_order_route(uuid: str):
    from app.domain.billing.models import Order
    order = Order.query.filter_by(uuid=uuid).first()
    if not order:
        return jsonify({"error": "Bestellung nicht gefunden"}), 404
    return jsonify(order.to_dict(include_user=True))


@admin_bp.route("/orders/<string:uuid>/mark-paid", methods=["POST"])
def mark_order_paid_route(uuid: str):
    """Bestellung als bezahlt markieren und Instance bereitstellen (manueller Zahlungsweg).

    Body: {"payment_reference": "Ueberweisung 2026-10-03"} (bei der ersten Zahlung optional).
    - pending_payment: erste Zahlung, Instance wird bereitgestellt
    - awaiting_provisioning: Instance wird erneut bereitgestellt (Zahlung nicht doppelt verbucht)
    - active / past_due: Verlaengerung um eine Laufzeit; `payment_reference` ist Pflicht (400) und
      macht den Aufruf idempotent: dieselbe Referenz verlaengert nie zweimal
    """
    from app.domain.auth.service import get_current_user
    from app.domain.billing.models import Order
    from app.domain.billing.service import BillingError, mark_order_paid
    order = Order.query.filter_by(uuid=uuid).first()
    if not order:
        return jsonify({"error": "Bestellung nicht gefunden"}), 404
    data = request.get_json(silent=True) or {}
    ref = data.get("payment_reference")
    if ref is not None and not isinstance(ref, str):
        return jsonify({"error": "Field 'payment_reference' must be a string"}), 400
    actor = get_current_user()
    try:
        order = mark_order_paid(order, ref, actor.id if actor else None)
    except BillingError as e:
        return _billing_error(e)
    return jsonify(order.to_dict(include_user=True))


@admin_bp.route("/orders/<string:uuid>/remind", methods=["POST"])
def remind_order_route(uuid: str):
    """Schickt dem Kunden eine Zahlungserinnerung (in seiner Sprache), hoechstens eine manuelle je Bestellung und 24 Stunden.

    Erlaubt bei active (Erinnerung vor Laufzeitende), past_due (Zahlung ueberfaellig) und pending_payment
    (Zahlung noch offen). Antwort 200 {sent_at, kind: expiry_reminder|past_due|payment_open}.
    Fehler: 404 unbekannt, 409 (`invalid_status`, `nothing_to_pay`, `cancelled`, `no_email`),
    429 {code: reminder_cooldown, retry_after_seconds}.
    """
    from app.domain.auth.service import get_current_user
    from app.domain.billing.models import Order
    from app.domain.billing.service import BillingError, send_manual_reminder
    order = Order.query.filter_by(uuid=uuid).first()
    if not order:
        return jsonify({"error": "Bestellung nicht gefunden"}), 404
    actor = get_current_user()
    try:
        result = send_manual_reminder(order, actor.id if actor else None)
    except BillingError as e:
        return _billing_error(e)
    return jsonify(result)


# ── Endpoints ───────────────────────────────────────────


@admin_bp.route("/endpoints", methods=["GET"])
def list_endpoints():
    endpoints = Endpoint.query.order_by(Endpoint.agent_id, Endpoint.port).all()
    return jsonify([e.to_dict() for e in endpoints])


@admin_bp.route("/agents/<int:agent_id>/endpoints", methods=["POST"])
def create_endpoint(agent_id: int):
    """Erstellt einen neuen Endpoint für einen Agent."""
    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify({"error": f"Agent mit ID {agent_id} nicht gefunden"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    port = data.get("port")
    if port is None:
        return jsonify({"error": "Field 'port' is required"}), 400

    ip = data.get("ip", "0.0.0.0")

    # Prüfen ob Port bereits auf diesem Agent vergeben ist
    existing = Endpoint.query.filter_by(agent_id=agent_id, ip=ip, port=port).first()
    if existing:
        return jsonify({"error": f"Endpoint {ip}:{port} existiert bereits auf diesem Agent"}), 409

    endpoint = Endpoint(
        agent_id=agent_id,
        ip=ip,
        port=port,
        is_locked=data.get("is_locked", False),
    )
    db.session.add(endpoint)
    db.session.commit()

    return jsonify(endpoint.to_dict()), 201


MAX_BULK_ENDPOINTS = 1000


def _instance_conn_load():
    """Laedt Agent und primaeren Endpoint mit, damit `connection` keine Query pro Instanz ausloest."""
    from sqlalchemy.orm import joinedload
    return [joinedload(Instance.agent), joinedload(Instance.primary_endpoint)]


@admin_bp.route("/agents/<int:agent_id>/endpoints/bulk", methods=["POST"])
def create_endpoints_bulk(agent_id: int):
    """Legt einen Port-Bereich als Endpoints an (M39).

    Body: {"ip": "0.0.0.0", "port_start": 25565, "port_end": 25600}
    Bereits vorhandene Kombinationen aus ip und port werden uebersprungen.
    Antwort: {"created": n, "skipped": n, "endpoints": [<neu angelegte>]}
    """
    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify({"error": f"Agent mit ID {agent_id} nicht gefunden"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body is required"}), 400

    start, end = data.get("port_start"), data.get("port_end")
    for label, value in (("port_start", start), ("port_end", end)):
        if isinstance(value, bool) or not isinstance(value, int):
            return jsonify({"error": f"Field '{label}' must be an integer"}), 400
        if not 1 <= value <= 65535:
            return jsonify({"error": f"Field '{label}' must be between 1 and 65535"}), 400
    if start > end:
        return jsonify({"error": "port_start must be <= port_end"}), 400
    count = end - start + 1
    if count > MAX_BULK_ENDPOINTS:
        return jsonify({"error": f"Maximal {MAX_BULK_ENDPOINTS} Ports pro Aufruf (angefragt: {count})"}), 400

    ip = data.get("ip", "0.0.0.0")
    try:
        ipaddress.ip_address(ip)
    except (ValueError, TypeError):
        return jsonify({"error": "Field 'ip' must be a valid IPv4/IPv6 address"}), 400

    existing = {
        port for (port,) in db.session.query(Endpoint.port).filter(
            Endpoint.agent_id == agent_id, Endpoint.ip == ip,
            Endpoint.port >= start, Endpoint.port <= end,
        )
    }
    new = [Endpoint(agent_id=agent_id, ip=ip, port=port)
           for port in range(start, end + 1) if port not in existing]
    db.session.add_all(new)
    db.session.commit()

    return jsonify({
        "created": len(new),
        "skipped": len(existing),
        "endpoints": [e.to_dict() for e in new],
    }), 201 if new else 200


# ── Instances ───────────────────────────────────────────


@admin_bp.route("/instances", methods=["GET"])
def list_instances():
    instances = (
        Instance.query.options(*_instance_conn_load())
        .order_by(Instance.created_at.desc()).all()
    )
    return jsonify([i.to_dict() for i in instances])


@admin_bp.route("/instances", methods=["POST"])
def create_instance_route():
    """
    Erstellt eine neue Instance.
    Validiert Agent, Blueprint, Owner und Endpoint über den Instance-Service.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # agent_id ist optional: fehlt es oder ist null, platziert Astra automatisch (M42)
    required = ["name", "owner_id", "blueprint_id"]
    missing = [f for f in required if f not in data or data[f] is None]
    if missing:
        return jsonify({"error": f"Required fields missing: {', '.join(missing)}"}), 400

    try:
        instance = create_instance(
            name=data["name"],
            owner_id=data["owner_id"],
            agent_id=data.get("agent_id"),
            blueprint_id=data["blueprint_id"],
            description=data.get("description"),
            endpoint_id=data.get("endpoint_id"),
            memory=data.get("memory", 512),
            swap=data.get("swap", 0),
            disk=data.get("disk", 1024),
            io=data.get("io", 500),
            cpu=data.get("cpu", 100),
            image=data.get("image"),
            startup_command=data.get("startup_command"),
            variable_values=data.get("variable_values"),
        )
        return jsonify(instance.to_dict()), 201

    except InstanceCreationError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/instances/<string:uuid>", methods=["DELETE"])
def delete_instance_route(uuid: str):
    """Loescht eine Instance samt abhaengiger Daten (M43).

    Optionaler Body: {"force": true} erzwingt das Loeschen auch waehrend laufender
    Vorgaenge (provisioning/reinstalling/restoring/transferring).
    """
    from app.domain.auth.service import get_current_user
    from app.domain.instances.service import delete_instance

    instance = Instance.query.filter_by(uuid=uuid).first()
    if not instance:
        return jsonify({"error": "Instance nicht gefunden"}), 404

    data = request.get_json(silent=True) or {}
    actor = get_current_user()
    try:
        result = delete_instance(instance, actor.id if actor else None, force=data.get("force") is True)
    except InstanceActionError as e:
        return jsonify({"error": e.message}), e.status_code
    return jsonify({**result, "message": "Instance geloescht"})


@admin_bp.route("/instances/<string:uuid>/backups", methods=["GET"])
def list_instance_backups_admin(uuid: str):
    """Backups einer Instance fuer Admins (z.B. Pruefung vor einem Transfer)."""
    from app.domain.backups.service import list_backups
    instance = Instance.query.filter_by(uuid=uuid).first()
    if not instance:
        return jsonify({"error": "Instance nicht gefunden"}), 404
    from app.utils.timeutil import iso_utc
    backups = list_backups(instance)
    successful = [b for b in backups if b.is_successful]
    times = [(b.completed_at or b.created_at) for b in successful if (b.completed_at or b.created_at)]
    return jsonify({
        "backups": [b.to_dict() for b in backups],
        "successful_count": len(successful),
        "last_successful_backup_at": iso_utc(max(times)) if times else None,
    })


@admin_bp.route("/instances/<string:uuid>/transfer", methods=["POST"])
def transfer_instance_route(uuid: str):
    """Transferiert eine Instance auf einen anderen Agent.

    Body: {"target_agent_id": int}
    """
    instance = Instance.query.filter_by(uuid=uuid).first()
    if not instance:
        return jsonify({"error": "Instance nicht gefunden"}), 404

    data = request.get_json()
    if not data or "target_agent_id" not in data:
        return jsonify({"error": "Field 'target_agent_id' is required"}), 400

    try:
        result = transfer_instance(instance, int(data["target_agent_id"]))
        return jsonify(result.to_dict())
    except InstanceActionError as e:
        return jsonify({"error": e.message}), e.status_code


# ── Suspension (M29) ────────────────────────────────────


@admin_bp.route("/instances/<string:uuid>/suspend", methods=["POST"])
def suspend_instance_route(uuid: str):
    """Suspendiert eine Instance administrativ.

    Nur Admins. Body optional: {"reason": "..."}
    """
    from app.domain.auth.service import require_admin
    admin, err = require_admin()
    if err:
        return err

    instance = Instance.query.filter_by(uuid=uuid).first()
    if not instance:
        return jsonify({"error": "Instance nicht gefunden"}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get("reason")

    result = suspend_instance(instance, admin.id, reason=reason)
    return jsonify({
        "message": "Instance suspendiert",
        "instance": result.to_dict(),
    })


@admin_bp.route("/instances/<string:uuid>/unsuspend", methods=["POST"])
def unsuspend_instance_route(uuid: str):
    """Hebt die Suspension einer Instance auf.

    Nur Admins.
    """
    from app.domain.auth.service import require_admin
    admin, err = require_admin()
    if err:
        return err

    instance = Instance.query.filter_by(uuid=uuid).first()
    if not instance:
        return jsonify({"error": "Instance nicht gefunden"}), 404

    result = unsuspend_instance(instance, admin.id)
    return jsonify({
        "message": "Suspension aufgehoben",
        "instance": result.to_dict(),
    })


# ── Activity ────────────────────────────────────────────


@admin_bp.route("/activity", methods=["GET"])
def admin_activity():
    """Listet alle Activity-Logs (paginiert, filterbar)."""
    from app.domain.activity.service import list_global

    event = request.args.get("event")
    actor_id = request.args.get("actor_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)

    result = list_global(event=event, actor_id=actor_id, page=page, per_page=per_page)
    return jsonify(result)


# ── Webhooks ────────────────────────────────────────────


@admin_bp.route("/webhooks", methods=["GET"])
def list_webhooks():
    """Listet alle Webhooks."""
    from app.domain.webhooks.service import list_webhooks as _list

    webhooks = _list()
    return jsonify([wh.to_dict() for wh in webhooks])


@admin_bp.route("/webhooks", methods=["POST"])
def create_webhook():
    """Erstellt einen neuen Webhook."""
    from app.domain.webhooks.service import create_webhook as _create, WebhookError

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    endpoint_url = data.get("endpoint_url")
    events = data.get("events")

    if not endpoint_url:
        return jsonify({"error": "Field 'endpoint_url' is required"}), 400
    if not events or not isinstance(events, list):
        return jsonify({"error": "Field 'events' must be a non-empty array"}), 400

    try:
        wh = _create(
            endpoint_url=endpoint_url,
            events=events,
            description=data.get("description"),
            secret_token=data.get("secret_token"),
            is_active=data.get("is_active", True),
        )
        return jsonify(wh.to_dict()), 201
    except WebhookError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/webhooks/<int:webhook_id>", methods=["PATCH"])
def update_webhook(webhook_id: int):
    """Aktualisiert einen Webhook."""
    from app.domain.webhooks.service import update_webhook as _update, WebhookError

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    try:
        wh = _update(webhook_id, **data)
        return jsonify(wh.to_dict())
    except WebhookError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/webhooks/<int:webhook_id>", methods=["DELETE"])
def delete_webhook(webhook_id: int):
    """Löscht einen Webhook."""
    from app.domain.webhooks.service import delete_webhook as _delete, WebhookError

    try:
        _delete(webhook_id)
        return jsonify({"message": "Webhook gelöscht"}), 200
    except WebhookError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/webhooks/<int:webhook_id>/test", methods=["POST"])
def test_webhook(webhook_id: int):
    """Sendet einen Test-Payload an einen Webhook."""
    from app.domain.webhooks.service import get_webhook, WebhookError
    from app.domain.webhooks.dispatcher import dispatch_test

    try:
        wh = get_webhook(webhook_id)
        result = dispatch_test(wh)
        return jsonify(result)
    except WebhookError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/webhooks/events", methods=["GET"])
def list_webhook_events():
    """Gibt den verfügbaren Event-Katalog zurück."""
    from app.domain.webhooks.event_catalog import get_event_catalog

    return jsonify(get_event_catalog())


# ── Fleet Monitoring (M22) ─────────────────────────────


@admin_bp.route("/agents/monitoring", methods=["GET"])
def agents_monitoring():
    """Fleet-Monitoring: Health, Kapazitaet, Auslastung aller Agents.

    Query-Parameter:
    - health: Filter nach Health-Status ('healthy', 'stale', 'degraded', 'unreachable')
    - search: Textsuche in Name/FQDN
    - stale_threshold: Schwellwert in Minuten (Default: 10)
    """
    from app.domain.agents.monitoring_service import get_all_agents_monitoring

    health_filter = request.args.get("health")
    search = request.args.get("search")
    stale_threshold = request.args.get("stale_threshold", 10, type=int)

    result = get_all_agents_monitoring(
        stale_threshold=stale_threshold,
        health_filter=health_filter,
        search=search,
    )
    return jsonify(result)


@admin_bp.route("/agents/<int:agent_id>/monitoring", methods=["GET"])
def agent_monitoring_detail(agent_id: int):
    """Monitoring-Daten fuer einen einzelnen Agent."""
    from app.domain.agents.monitoring_service import get_single_agent_monitoring

    stale_threshold = request.args.get("stale_threshold", 10, type=int)
    result = get_single_agent_monitoring(agent_id, stale_threshold)
    if result is None:
        return jsonify({"error": f"Agent mit ID {agent_id} nicht gefunden"}), 404
    return jsonify(result)


@admin_bp.route("/fleet/summary", methods=["GET"])
def fleet_summary():
    """Globale Fleet-Kennzahlen: Agents, Instances, Kapazitaet, Auslastung."""
    from app.domain.agents.monitoring_service import get_fleet_summary

    stale_threshold = request.args.get("stale_threshold", 10, type=int)
    result = get_fleet_summary(stale_threshold)
    return jsonify(result)


# ── Runner/System ───────────────────────────────────────


@admin_bp.route("/runner/info", methods=["GET"])
def runner_info():
    """Gibt Informationen zum aktiven Runner-Adapter zurück."""
    from flask import current_app

    adapter = current_app.config.get("_RUNNER_ADAPTER_NAME", "unknown")
    timeout_connect = current_app.config.get("RUNNER_TIMEOUT_CONNECT", 5)
    timeout_read = current_app.config.get("RUNNER_TIMEOUT_READ", 30)
    debug = current_app.config.get("RUNNER_DEBUG", False)

    return jsonify({
        "adapter": adapter,
        "timeout": {"connect": timeout_connect, "read": timeout_read},
        "debug": debug,
    })


# ── Database Providers (M18) ───────────────────────────


@admin_bp.route("/database-providers", methods=["GET"])
def list_database_providers():
    from app.domain.databases.service import list_providers
    return jsonify([p.to_dict() for p in list_providers()])


@admin_bp.route("/database-providers", methods=["POST"])
def create_database_provider():
    from app.domain.databases.service import create_provider, DatabaseError

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    try:
        provider = create_provider(
            name=data.get("name", ""),
            host=data.get("host", ""),
            port=data.get("port", 3306),
            admin_user=data.get("admin_user", "root"),
            admin_password=data.get("admin_password"),
            max_databases=data.get("max_databases"),
        )
        return jsonify(provider.to_dict()), 201
    except DatabaseError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/database-providers/<int:provider_id>", methods=["PATCH"])
def update_database_provider(provider_id: int):
    from app.domain.databases.service import update_provider, DatabaseError

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    try:
        provider = update_provider(provider_id, **data)
        return jsonify(provider.to_dict())
    except DatabaseError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/database-providers/<int:provider_id>", methods=["DELETE"])
def delete_database_provider(provider_id: int):
    from app.domain.databases.service import delete_provider, DatabaseError

    try:
        delete_provider(provider_id)
        return jsonify({"message": "Provider geloescht"})
    except DatabaseError as e:
        return jsonify({"error": e.message}), e.status_code


# ── Jobs (M23) ─────────────────────────────────────────


@admin_bp.route("/jobs", methods=["GET"])
def list_jobs():
    """Listet Hintergrundjobs mit optionalen Filtern.

    Query-Parameter:
    - status: Filter nach Status ('pending', 'running', 'completed', 'failed', 'retrying')
    - type: Filter nach Job-Typ
    - page: Seite (Default: 1)
    - per_page: Eintraege pro Seite (Default: 50)
    """
    from app.infrastructure.jobs.models import JobRecord, JobStatus

    query = JobRecord.query.order_by(JobRecord.created_at.desc())

    status_filter = request.args.get("status")
    if status_filter and status_filter in JobStatus.ALL:
        query = query.filter(JobRecord.status == status_filter)

    type_filter = request.args.get("type")
    if type_filter:
        query = query.filter(JobRecord.job_type == type_filter)

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [j.to_dict() for j in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "per_page": paginated.per_page,
        "pages": paginated.pages,
    })


@admin_bp.route("/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id: int):
    """Details eines einzelnen Jobs."""
    from app.infrastructure.jobs.models import JobRecord

    job = db.session.get(JobRecord, job_id)
    if not job:
        return jsonify({"error": f"Job mit ID {job_id} nicht gefunden"}), 404
    return jsonify(job.to_dict())


@admin_bp.route("/jobs/summary", methods=["GET"])
def jobs_summary():
    """Zusammenfassung der Job-Statistiken."""
    from app.infrastructure.jobs.models import JobRecord, JobStatus
    from sqlalchemy import func

    counts = (
        db.session.query(JobRecord.status, func.count(JobRecord.id))
        .group_by(JobRecord.status)
        .all()
    )
    status_counts = {status: count for status, count in counts}

    type_counts = (
        db.session.query(JobRecord.job_type, func.count(JobRecord.id))
        .group_by(JobRecord.job_type)
        .all()
    )

    return jsonify({
        "total": sum(status_counts.values()),
        "by_status": status_counts,
        "by_type": {jtype: count for jtype, count in type_counts},
    })


# ── System / Version (M24) ─────────────────────────────


@admin_bp.route("/system/version", methods=["GET"])
def system_version():
    """Versions- und Build-Informationen."""
    from app.version import get_version_info, VERSION

    info = get_version_info()
    from flask import current_app
    info["environment"] = current_app.config.get("APP_ENV", "unknown")
    info["service"] = "astra-backend"
    return jsonify(info)


@admin_bp.route("/system/upgrade-status", methods=["GET"])
def system_upgrade_status():
    """Upgrade-Status: Version, Migration, Kompatibilitaet."""
    from app.domain.system.upgrade_service import get_upgrade_status
    return jsonify(get_upgrade_status())


@admin_bp.route("/system/preflight", methods=["GET"])
def system_preflight():
    """Preflight-Check: Konfiguration, DB, Migrationen, Redis."""
    from app.domain.system.upgrade_service import run_preflight_check
    result = run_preflight_check()
    status_code = 200 if result["compatible"] else 503
    return jsonify(result), status_code


# ── Agent Maintenance (M25) ────────────────────────────


@admin_bp.route("/agents/<int:agent_id>/maintenance", methods=["POST"])
def enable_agent_maintenance(agent_id: int):
    """Setzt einen Agent in den Maintenance-Modus."""
    from app.domain.agents.maintenance_service import enable_maintenance, MaintenanceError

    data = request.get_json(silent=True) or {}
    reason = data.get("reason")

    try:
        agent = enable_maintenance(agent_id, reason=reason)
        return jsonify({
            "message": f"Agent '{agent.name}' in Maintenance gesetzt",
            "agent": agent.to_dict(),
        })
    except MaintenanceError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/agents/<int:agent_id>/maintenance", methods=["DELETE"])
def disable_agent_maintenance(agent_id: int):
    """Nimmt einen Agent aus dem Maintenance-Modus."""
    from app.domain.agents.maintenance_service import disable_maintenance, MaintenanceError

    try:
        agent = disable_maintenance(agent_id)
        return jsonify({
            "message": f"Agent '{agent.name}' aus Maintenance genommen",
            "agent": agent.to_dict(),
        })
    except MaintenanceError as e:
        return jsonify({"error": e.message}), e.status_code


@admin_bp.route("/agents/<int:agent_id>/maintenance", methods=["PATCH"])
def update_agent_maintenance(agent_id: int):
    """Aktualisiert den Maintenance-Grund."""
    from app.domain.agents.maintenance_service import MaintenanceError

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify({"error": f"Agent mit ID {agent_id} nicht gefunden"}), 404

    data = request.get_json(silent=True) or {}
    if "reason" in data:
        agent.maintenance_reason = data["reason"]
        db.session.commit()

    return jsonify({
        "message": f"Maintenance-Grund aktualisiert",
        "agent": agent.to_dict(),
    })
