"""Admin-API-Routen (inkl. M22 Fleet Monitoring)."""

from flask import Blueprint, jsonify, request
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.blueprints.models import Blueprint as BlueprintModel
from app.domain.users.models import User
from app.domain.instances.models import Instance
from app.domain.endpoints.models import Endpoint
from app.domain.instances.service import create_instance, InstanceCreationError

admin_bp = Blueprint("admin", __name__)


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
            "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
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
    db.session.add(agent)
    db.session.commit()

    return jsonify(agent.to_dict()), 201


# ── Blueprints ──────────────────────────────────────────


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

    blueprint = BlueprintModel(
        name=name,
        description=data.get("description"),
        docker_image=data.get("docker_image"),
        config_schema=data.get("config_schema"),
    )
    db.session.add(blueprint)
    db.session.commit()

    return jsonify(blueprint.to_dict()), 201


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


# ── Instances ───────────────────────────────────────────


@admin_bp.route("/instances", methods=["GET"])
def list_instances():
    instances = Instance.query.order_by(Instance.created_at.desc()).all()
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

    required = ["name", "owner_id", "agent_id", "blueprint_id"]
    missing = [f for f in required if f not in data or data[f] is None]
    if missing:
        return jsonify({"error": f"Required fields missing: {', '.join(missing)}"}), 400

    try:
        instance = create_instance(
            name=data["name"],
            owner_id=data["owner_id"],
            agent_id=data["agent_id"],
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
        )
        return jsonify(instance.to_dict()), 201

    except InstanceCreationError as e:
        return jsonify({"error": e.message}), e.status_code


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
