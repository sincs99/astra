"""Produkte und Bestellungen (M44).

Ablauf: Kunde bestellt (pending_payment) -> Zahlung bestaetigt (heute manuell durch den Admin,
spaeter Zahlungsanbieter) -> Instance wird automatisch platziert und angelegt (active).
Ressourcen und Preis kommen immer aus dem Schnappschuss der Bestellung, nie vom Kunden.
"""

from __future__ import annotations

import logging
import re
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.domain.billing.models import (
    Order, Product,
    ORDER_PENDING_PAYMENT, ORDER_AWAITING_PROVISIONING, ORDER_ACTIVE,
    ORDER_PAST_DUE, ORDER_CANCELLED, ORDER_EXPIRED, ORDER_COUNTING_STATUSES,
)
from app.domain.blueprints.models import Blueprint
from app.domain.instances.models import Instance
from app.domain.users.models import User
from app.utils.timeutil import iso_utc

logger = logging.getLogger(__name__)

MAX_PENDING_ORDERS_PER_USER = 5
# Suspendierungsgrund bei ueberfaelliger Zahlung: nur Suspensions mit genau diesem Grund hebt eine
# Verlaengerung wieder auf (eine Admin-Sperre z.B. wegen Missbrauch bleibt bestehen)
PAYMENT_SUSPEND_REASON = "Zahlung überfällig"
# So lange wartet der Tick bei laufender Installation/Transfer/Wiederherstellung, bevor er trotzdem sperrt
# (ein Install-Callback wuerde eine zu frueh gesetzte Sperre sonst stillschweigend aufheben)
BLOCKED_STATUS_WAIT = timedelta(days=1)
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class BillingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    """Naive UTC wie die DateTime-Spalten (keine Serverzeitzonen-Effekte)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# ── Produkte ────────────────────────────────────────────


def _int(data: dict, field: str, minimum: int, maximum: int | None = None) -> int:
    value = data[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise BillingError(f"Field '{field}' must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        rng = f">= {minimum}" if maximum is None else f"between {minimum} and {maximum}"
        raise BillingError(f"Field '{field}' must be {rng}")
    return value


def clean_product_data(data: dict, partial: bool) -> dict:
    """Validiert Produktfelder. Bei partial=True (PATCH) sind alle Felder optional."""
    required = ("name", "blueprint_id", "memory", "disk", "cpu")
    if not partial:
        missing = [f for f in required if data.get(f) is None]
        if missing:
            raise BillingError(f"Required fields missing: {', '.join(missing)}")

    out: dict = {}
    if "name" in data:
        name = data["name"]
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            raise BillingError("Field 'name' must be a non-empty string (max 120 chars)")
        out["name"] = name.strip()
    if "description" in data:
        if data["description"] is not None and not isinstance(data["description"], str):
            raise BillingError("Field 'description' must be a string")
        out["description"] = data["description"]
    if "blueprint_id" in data:
        bp_id = _int(data, "blueprint_id", 1)
        if not db.session.get(Blueprint, bp_id):
            raise BillingError(f"Blueprint {bp_id} nicht gefunden", 404)
        out["blueprint_id"] = bp_id
    for field, minimum, maximum in (("memory", 1, None), ("disk", 1, None), ("cpu", 1, None),
                                    ("swap", 0, None), ("io", 10, 1000),
                                    ("price_cents", 0, None), ("billing_period_days", 1, 3650)):
        if field in data:
            out[field] = _int(data, field, minimum, maximum)
    if "currency" in data:
        currency = data["currency"]
        if not isinstance(currency, str) or not _CURRENCY_RE.match(currency.upper()):
            raise BillingError("Field 'currency' must be a 3-letter ISO code")
        out["currency"] = currency.upper()
    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            raise BillingError("Field 'is_active' must be a boolean")
        out["is_active"] = data["is_active"]
    if "max_instances_per_user" in data:
        if data["max_instances_per_user"] is None:
            out["max_instances_per_user"] = None
        else:
            out["max_instances_per_user"] = _int(data, "max_instances_per_user", 1)
    return out


def _check_free_product_limit(price_cents: int, max_per_user: int | None) -> None:
    if price_cents == 0 and max_per_user is None:
        raise BillingError(
            "Kostenlose Produkte brauchen max_instances_per_user (sonst unbegrenzt viele Gratis-Server)"
        )


def create_product(data: dict) -> Product:
    fields = clean_product_data(data, partial=False)
    fields.setdefault("price_cents", 0)
    _check_free_product_limit(fields["price_cents"], fields.get("max_instances_per_user"))
    product = Product(**fields)
    db.session.add(product)
    db.session.commit()
    return product


def update_product(product: Product, data: dict) -> Product:
    fields = clean_product_data(data, partial=True)
    price = fields.get("price_cents", product.price_cents)
    limit = fields["max_instances_per_user"] if "max_instances_per_user" in fields else product.max_instances_per_user
    _check_free_product_limit(price, limit)
    for key, value in fields.items():
        setattr(product, key, value)
    db.session.commit()
    return product


def delete_product(product: Product) -> None:
    if Order.query.filter_by(product_id=product.id).first():
        raise BillingError("Produkt hat Bestellungen und kann nicht gelöscht werden – bitte deaktivieren", 409)
    db.session.delete(product)
    db.session.commit()


# ── Bestellungen ────────────────────────────────────────


def _log(event: str, order: Order, actor_id: int | None, description: str, extra: dict | None = None) -> None:
    try:
        from app.domain.activity.service import log_event
        log_event(event=event, actor_id=actor_id, subject_id=order.id, subject_type="order",
                  description=description,
                  properties={"order_uuid": order.uuid, "user_id": order.user_id,
                              "product_id": order.product_id, "status": order.status, **(extra or {})})
    except Exception:  # pragma: no cover - Logging darf Bestellungen nie blockieren
        logger.exception("Activity-Logging fuer Bestellung %s fehlgeschlagen", order.uuid)


def _clean_instance_name(name, product: Product) -> str:
    if name is None or (isinstance(name, str) and not name.strip()):
        return f"{product.name} {_uuid.uuid4().hex[:6]}"[:120]
    if not isinstance(name, str) or len(name.strip()) > 120:
        raise BillingError("Field 'name' must be a string (max 120 chars)")
    return name.strip()


def create_order(user: User, product_id, name=None) -> Order:
    """Legt eine Bestellung an. Kostenlose Produkte werden sofort bereitgestellt."""
    if isinstance(product_id, bool) or not isinstance(product_id, int):
        raise BillingError("Field 'product_id' must be an integer")
    product = db.session.get(Product, product_id)
    if not product or not product.is_active:
        raise BillingError("Produkt nicht gefunden", 404)

    instance_name = _clean_instance_name(name, product)

    pending = Order.query.filter_by(user_id=user.id, status=ORDER_PENDING_PAYMENT).count()
    if pending >= MAX_PENDING_ORDERS_PER_USER:
        raise BillingError(
            f"Zu viele offene Bestellungen ({MAX_PENDING_ORDERS_PER_USER}) – bitte erst bezahlen oder stornieren", 409
        )
    if product.max_instances_per_user is not None:
        used = Order.query.filter(
            Order.user_id == user.id, Order.product_id == product.id,
            Order.status.in_(ORDER_COUNTING_STATUSES),
        ).count()
        if used >= product.max_instances_per_user:
            raise BillingError(
                f"Limit erreicht: maximal {product.max_instances_per_user} Server dieses Pakets pro Kunde", 409
            )

    order = Order(
        user_id=user.id, product_id=product.id, status=ORDER_PENDING_PAYMENT,
        instance_name=instance_name, price_cents=product.price_cents, currency=product.currency,
        billing_period_days=product.billing_period_days,
        snapshot={"product_name": product.name, "blueprint_id": product.blueprint_id, **product.resources()},
    )
    db.session.add(order)
    db.session.commit()
    _log("order:created", order, user.id, f"Bestellung '{product.name}' angelegt")

    if order.price_cents == 0:
        try:
            mark_order_paid(order, payment_reference="free", actor_id=None)
        except BillingError as e:
            # Gratis-Bestellung bleibt als awaiting_provisioning erhalten (z.B. kein Platz auf den Nodes);
            # der Admin kann sie ueber "bezahlt" erneut bereitstellen
            logger.warning("Gratis-Bestellung %s nicht bereitgestellt: %s", order.uuid, e.message)
        order = db.session.get(Order, order.id)
    return order


def fulfill_order(order: Order, now: datetime | None = None, log_failure: bool = True) -> Order:
    """Legt die Instance einer bezahlten Bestellung an (automatische Platzierung).

    Die Laufzeit beginnt mit der Bereitstellung, nicht mit der Zahlung: Wartet eine bezahlte Bestellung
    auf einen freien Node, verliert der Kunde dadurch keine Zeit. `log_failure=False` unterdrueckt das
    Event `order:provision_failed` (fuer die automatische Wiederholung im Tick, sonst eins pro Lauf).
    """
    now = _utc_naive(now) or _now()
    from app.domain.instances.service import create_instance, InstanceCreationError

    snap = order.snapshot
    try:
        instance = create_instance(
            name=order.instance_name, owner_id=order.user_id, agent_id=None,
            blueprint_id=snap["blueprint_id"],
            memory=snap["memory"], swap=snap["swap"], disk=snap["disk"], io=snap["io"], cpu=snap["cpu"],
        )
    except InstanceCreationError as e:
        db.session.rollback()
        order = db.session.get(Order, order.id)
        order.status = ORDER_AWAITING_PROVISIONING
        db.session.commit()
        if log_failure:
            _log("order:provision_failed", order, None, f"Instance konnte nicht angelegt werden: {e.message}",
                 {"reason": e.message})
        raise BillingError(f"Bestellung bezahlt, aber Instance konnte nicht angelegt werden: {e.message}", 409)

    order.instance_id = instance.id
    order.status = ORDER_ACTIVE
    order.current_period_end = now + timedelta(days=order.billing_period_days)
    order.past_due_at = None
    db.session.commit()
    return order


def mark_order_paid(order: Order, payment_reference: str | None = None, actor_id: int | None = None,
                    now: datetime | None = None) -> Order:
    """Zahlung bestaetigen.

    - pending_payment: erste Zahlung, Instance wird bereitgestellt
    - awaiting_provisioning: Instance erneut bereitstellen, Zahlung nicht doppelt verbuchen
    - active / past_due: Verlaengerung um eine Laufzeit (siehe renew_order), erfordert `payment_reference`
    """
    # Zeilensperre: zwei gleichzeitige Aufrufe duerfen nur einmal verbuchen/bereitstellen (PostgreSQL)
    order = db.session.query(Order).filter_by(id=order.id).with_for_update().one()
    now = _utc_naive(now) or _now()
    ref = (payment_reference or "").strip()[:191] or None

    if order.status in (ORDER_ACTIVE, ORDER_PAST_DUE):
        return renew_order(order, ref, actor_id, now)
    if order.status not in (ORDER_PENDING_PAYMENT, ORDER_AWAITING_PROVISIONING):
        raise BillingError(f"Bestellung im Status '{order.status}' kann nicht als bezahlt markiert werden", 409)

    if order.status == ORDER_PENDING_PAYMENT:
        order.paid_at = now
        order.payment_reference = ref
        order.payment_references = [ref] if ref else []
        db.session.commit()
        _log("order:paid", order, actor_id, "Bestellung als bezahlt markiert", {"payment_reference": ref})
    return fulfill_order(order, now)


def renew_order(order: Order, payment_reference: str | None, actor_id: int | None = None,
                now: datetime | None = None) -> Order:
    """Verlaengert eine aktive oder ueberfaellige Bestellung um eine Laufzeit.

    Das neue Ende zaehlt ab max(jetzt, bisheriges Ende): Vorauszahlungen verfallen nicht, eine verspaetete
    Zahlung verschenkt aber keine Zeit. Eine bereits verbuchte `payment_reference` ist ein No-op, so
    entsteht bei Doppelklick oder Wiederholung keine zweite Verlaengerung. Eine Suspendierung wegen
    ueberfaelliger Zahlung wird aufgehoben, eine Admin-Sperre aus anderem Grund bleibt bestehen.
    Eine vorgemerkte Kuendigung (cancel_at_period_end) bleibt erhalten.
    """
    now = _utc_naive(now) or _now()
    if not payment_reference:
        raise BillingError(
            "Für eine Verlängerung ist 'payment_reference' erforderlich (verhindert doppeltes Verbuchen)", 400
        )
    refs = list(order.payment_references or [])
    if payment_reference in refs:
        return order  # diese Zahlung ist schon verbucht

    instance = db.session.get(Instance, order.instance_id) if order.instance_id else None
    if instance is None:
        raise BillingError("Die Instance dieser Bestellung existiert nicht mehr – keine Verlängerung möglich", 409)

    was_past_due = order.status == ORDER_PAST_DUE
    base = max(now, order.current_period_end or now)
    order.current_period_end = base + timedelta(days=order.billing_period_days)
    order.payment_reference = payment_reference
    order.payment_references = refs + [payment_reference]
    order.status = ORDER_ACTIVE
    order.past_due_at = None
    db.session.commit()

    lifted = False
    from app.domain.instances.service import STATUS_SUSPENDED
    if instance.status == STATUS_SUSPENDED and instance.suspended_reason == PAYMENT_SUSPEND_REASON:
        from app.domain.instances.service import unsuspend_instance, sync_instance
        unsuspend_instance(instance, actor_id)
        _best_effort(sync_instance, instance)
        lifted = True

    _log("order:renewed", order, actor_id, "Bestellung verlängert",
         {"payment_reference": payment_reference, "was_past_due": was_past_due, "unsuspended": lifted,
          "current_period_end": iso_utc(order.current_period_end)})
    return order


def _best_effort(func, *args):
    try:
        return func(*args)
    except Exception as e:  # pragma: no cover - Netzwerk-/Runner-Fehler duerfen den Ablauf nie stoppen
        logger.warning("%s fehlgeschlagen (best effort): %s", getattr(func, "__name__", func), e)
        return None


def cancel_order(order: Order, actor_id: int | None = None) -> Order:
    """Kunde storniert: offene Bestellung sofort, aktive zum Laufzeitende (Server laeuft weiter)."""
    if order.status == ORDER_PENDING_PAYMENT:
        order.status = ORDER_CANCELLED
        order.cancelled_at = _now()
        db.session.commit()
        _log("order:cancelled", order, actor_id, "Offene Bestellung storniert")
    elif order.status in (ORDER_ACTIVE, ORDER_PAST_DUE):
        if not order.cancel_at_period_end:
            order.cancel_at_period_end = True
            order.cancelled_at = _now()
            db.session.commit()
            _log("order:cancelled", order, actor_id, "Kündigung zum Laufzeitende vorgemerkt")
    elif order.status == ORDER_AWAITING_PROVISIONING:
        raise BillingError("Bezahlte Bestellung wird noch bereitgestellt – bitte den Support kontaktieren", 409)
    else:
        raise BillingError(f"Bestellung im Status '{order.status}' kann nicht storniert werden", 409)
    return order


# ── Instance geloescht: verknuepfte Bestellungen beenden (M46) ──


def detach_orders_from_instance(instance_id: int) -> list[int]:
    """Loest Bestellungen von einer Instance, die gleich geloescht wird (ohne Commit).

    Noetig wegen der Fremdschluessel-Beziehung orders.instance_id -> instances.id. Lebende Bestellungen
    (active, past_due) sind danach `expired`: ohne Server gibt es nichts mehr zu verlaengern.
    Rueckgabe: IDs der beendeten Bestellungen (fuer das Activity-Event nach dem Commit).
    """
    expired = []
    for order in Order.query.filter_by(instance_id=instance_id).all():
        order.instance_id = None
        if order.status in (ORDER_ACTIVE, ORDER_PAST_DUE):
            order.status = ORDER_EXPIRED
            order.past_due_at = None
            expired.append(order.id)
    return expired


def log_orders_expired(order_ids: list[int], reason: str) -> None:
    for order_id in order_ids:
        order = db.session.get(Order, order_id)
        if order:
            _log("order:expired", order, None, f"Bestellung beendet ({reason})", {"reason": reason})


# ── Betriebszustand des Billing-Ticks (M53) ─────────────

TICK_STATE_KEY = "billing_tick"
_LIVE_STATUSES = (ORDER_ACTIVE, ORDER_PAST_DUE, ORDER_AWAITING_PROVISIONING)


def _record_tick(summary: dict, now: datetime) -> None:
    """Merkt sich Zeitpunkt und Ergebnis des letzten Laufs (auch bei Fehlern), best effort."""
    from sqlalchemy.exc import IntegrityError
    from app.domain.system.models import SystemState
    value = {"last_run_at": iso_utc(now), "summary": summary}
    try:
        for _ in range(2):
            state = db.session.get(SystemState, TICK_STATE_KEY)
            if state is None:
                db.session.add(SystemState(key=TICK_STATE_KEY, value=value))
            else:
                state.value = value
            try:
                db.session.commit()
                return
            except IntegrityError:  # zwei Ticks haben gleichzeitig angelegt: noch einmal als Update
                db.session.rollback()
    except Exception:  # pragma: no cover - Ueberwachung darf den Tick nie stoeren
        db.session.rollback()
        logger.exception("Billing-Tick: Lauf konnte nicht vermerkt werden")


def get_tick_status(now: datetime | None = None) -> dict:
    """Laeuft der Billing-Tick? `healthy` ist nur relevant, solange es Bestellungen gibt, die der Tick braucht
    (aktiv, ueberfaellig oder wartend). Ohne solche Bestellungen ist ein fehlender Tick unkritisch."""
    from flask import current_app
    from app.domain.system.models import SystemState
    now = _utc_naive(now) or _now()
    max_age = int(current_app.config.get("BILLING_TICK_MAX_AGE_MINUTES", 15))

    state = db.session.get(SystemState, TICK_STATE_KEY)
    last_run, summary = None, None
    if state and isinstance(state.value, dict) and state.value.get("last_run_at"):
        last_run = _utc_naive(datetime.fromisoformat(state.value["last_run_at"]))
        summary = state.value.get("summary")
    age = (now - last_run).total_seconds() if last_run else None

    counts = dict(db.session.query(Order.status, db.func.count(Order.id)).group_by(Order.status).all())
    needing = sum(counts.get(s, 0) for s in _LIVE_STATUSES)
    healthy = needing == 0 or (age is not None and age <= max_age * 60)
    return {
        "healthy": healthy,
        "last_run_at": iso_utc(last_run),
        "age_seconds": int(age) if age is not None else None,
        "max_age_minutes": max_age,
        "orders_needing_tick": needing,
        "orders_by_status": counts,
        "last_summary": summary,
    }


# ── Billing-Tick (M46) ──────────────────────────────────


def _mail_order(order: Order, subject: str, body: str) -> None:
    try:
        from flask import current_app
        from app.infrastructure.mail import send_mail
        user = db.session.get(User, order.user_id)
        if user and user.email:
            send_mail(current_app, user.email, subject, body)
    except Exception:  # pragma: no cover - Mail darf den Tick nie stoppen
        logger.exception("Mail zur Bestellung %s fehlgeschlagen", order.uuid)


def _blocking_status(instance: Instance) -> bool:
    from app.domain.instances.service import _DELETE_BLOCKING_STATUSES
    return instance.status in _DELETE_BLOCKING_STATUSES


def _expire_order(order: Order, instance: Instance | None, reason: str) -> None:
    """Beendet eine Bestellung: Instance loeschen (falls vorhanden), Status expired, Mail."""
    if instance is not None:
        from app.domain.instances.service import delete_instance
        # delete_instance setzt die Bestellung auf expired, loest sie von der Instance und loggt order:expired
        delete_instance(instance, None, force=True, order_reason=reason)
        db.session.refresh(order)
    else:
        # Instance fehlt bereits: kein Runner-Aufruf, nur Status
        order.instance_id = None
        order.status = ORDER_EXPIRED
        order.past_due_at = None
        db.session.commit()
        log_orders_expired([order.id], reason)
    _mail_order(
        order, "Astra: Dein Server wurde beendet",
        f"Hallo,\n\ndein Server '{order.instance_name}' wurde beendet und gelöscht "
        f"({'Kündigung zum Laufzeitende' if reason == 'cancelled_at_period_end' else 'Zahlung nicht eingegangen'}).\n"
        f"Bestellung: {order.uuid}\n",
    )


def _suspend_for_payment(order: Order, instance: Instance, now: datetime) -> bool:
    """Ueberfaellige Bestellung: Instance sperren und stoppen. False = spaeter erneut versuchen."""
    from app.domain.instances.service import (
        STATUS_SUSPENDED, suspend_instance, sync_instance, send_power_action,
    )
    if _blocking_status(instance) and now < (order.current_period_end or now) + BLOCKED_STATUS_WAIT:
        return False  # laufende Installation/Transfer: bis zu einem Tag spaeter erneut versuchen

    # Eine bestehende Admin-Sperre (z.B. Missbrauch) nicht ueberschreiben
    newly_suspended = instance.status != STATUS_SUSPENDED
    if newly_suspended:
        suspend_instance(instance, None, PAYMENT_SUSPEND_REASON)

    order.status = ORDER_PAST_DUE
    order.past_due_at = now
    db.session.commit()

    if newly_suspended:
        # Wings kennt die Sperre erst nach dem Sync; der laufende Server wird zusaetzlich beendet
        _best_effort(sync_instance, instance)
        _best_effort(send_power_action, instance, "kill")

    _log("order:past_due", order, None, "Bestellung überfällig, Instance suspendiert",
         {"suspended": newly_suspended, "current_period_end": iso_utc(order.current_period_end)})
    from flask import current_app
    days = current_app.config.get("BILLING_GRACE_DAYS", 7)
    _mail_order(
        order, "Astra: Zahlung überfällig – dein Server wurde gesperrt",
        f"Hallo,\n\ndie Laufzeit deines Servers '{order.instance_name}' ist abgelaufen, der Server wurde gesperrt.\n"
        f"Bitte begleiche die Zahlung innerhalb von {days} Tagen, sonst wird er gelöscht.\n"
        f"Bestellung: {order.uuid}\n",
    )
    return True


def _nothing() -> None:
    db.session.rollback()  # Zeilensperre loesen
    return None


def _remind_if_due(order: Order, end: datetime, now: datetime, reminder: timedelta) -> bool:
    """Mail vor Laufzeitende, hoechstens einmal pro Order und Periode.

    - normale Bestellung: "Laufzeit endet bald, bitte zahlen" (nur bezahlte, Laufzeit laenger als das Fenster)
    - gekuendigte Bestellung: einmalig "Server wird am X geloescht"
    """
    cancelled = bool(order.cancel_at_period_end)
    if (reminder <= timedelta(0) or order.status != ORDER_ACTIVE
            or now < end - reminder or order.reminded_for_period_end == end):
        return False
    if not cancelled and (order.price_cents == 0 or timedelta(days=order.billing_period_days) <= reminder):
        return False
    order.reminded_for_period_end = end
    db.session.commit()  # erst markieren: bei einem Fehler danach lieber keine Mail als jeden Tick eine
    _log("order:reminder", order, None,
         "Löschhinweis vor Laufzeitende verschickt" if cancelled else "Erinnerung vor Laufzeitende verschickt",
         {"current_period_end": iso_utc(end), "kind": "deletion_notice" if cancelled else "expiry_reminder"})
    if cancelled:
        _mail_order(
            order, "Astra: Dein Server wird bald gelöscht",
            f"Hallo,\n\nwegen deiner Kündigung wird dein Server '{order.instance_name}' am "
            f"{end:%d.%m.%Y %H:%M} UTC gelöscht. Sichere vorher deine Dateien.\n"
            f"Bestellung: {order.uuid}\n",
        )
    else:
        _mail_order(
            order, "Astra: Die Laufzeit deines Servers endet bald",
            f"Hallo,\n\ndie Laufzeit deines Servers '{order.instance_name}' endet am {end:%d.%m.%Y %H:%M} UTC.\n"
            f"Bitte veranlasse rechtzeitig die Zahlung ({order.price_cents / 100:.2f} {order.currency} für "
            f"{order.billing_period_days} Tage), sonst wird der Server gesperrt und nach der Karenzzeit gelöscht.\n"
            f"Bestellung: {order.uuid}\n",
        )
    return True


def _process_order(order_id: int, now: datetime, grace: timedelta, reminder: timedelta | None = None) -> str | None:
    """Bearbeitet eine Bestellung. Rueckgabe: 'past_due', 'expired', 'reminded', 'renewed' oder None."""
    reminder = reminder if reminder is not None else timedelta(0)
    # Zeilensperre und Statuspruefung: ein parallel laufender Tick oder eine Zahlung darf nicht ueberfahren werden
    order = db.session.query(Order).filter_by(id=order_id).with_for_update().one()
    if order.status not in (ORDER_ACTIVE, ORDER_PAST_DUE):
        db.session.rollback()
        return None

    instance = db.session.get(Instance, order.instance_id) if order.instance_id else None
    if instance is None:
        _expire_order(order, None, "instance_missing")
        return "expired"

    end = order.current_period_end
    if end is None:
        raise RuntimeError("current_period_end fehlt")
    if end >= now:
        return "reminded" if _remind_if_due(order, end, now, reminder) else _nothing()

    if order.cancel_at_period_end:
        _expire_order(order, instance, "cancelled_at_period_end")
        return "expired"

    if order.price_cents == 0:
        # Kostenlose Pakete laufen weiter: der Kunde kann nichts bezahlen, also verlaengert der Tick selbst
        renew_order(order, f"free-auto:{end.isoformat()}", None, now)
        return "renewed"

    if order.status == ORDER_ACTIVE:
        return "past_due" if _suspend_for_payment(order, instance, now) else None

    # past_due: Karenzzeit laeuft seit past_due_at (nicht seit Laufzeitende, damit ein Ausfall des Ticks
    # den Kunden nicht um seine Karenzzeit bringt)
    if order.past_due_at is None:
        order.past_due_at = now
        db.session.commit()
        return None
    if order.past_due_at + grace <= now:
        _expire_order(order, instance, "grace_period_over")
        return "expired"
    db.session.rollback()
    return None


def _retry_provisioning(order_id: int, now: datetime) -> bool:
    """Stellt eine bezahlte Bestellung ohne Instance erneut bereit. True = jetzt bereitgestellt."""
    order = db.session.query(Order).filter_by(id=order_id).with_for_update().one()
    if order.status != ORDER_AWAITING_PROVISIONING or order.instance_id:
        db.session.rollback()
        return False  # inzwischen vom Admin oder einer Zahlung bereitgestellt
    try:
        fulfill_order(order, now, log_failure=False)
    except BillingError:
        return False  # weiterhin kein Platz: leise im naechsten Tick erneut
    order = db.session.get(Order, order_id)
    _log("order:provisioned", order, None, "Bezahlte Bestellung nachtraeglich automatisch bereitgestellt")
    instance = db.session.get(Instance, order.instance_id)
    info = instance.connection_info() if instance else None
    address = f"\nVerbindungsadresse: {info['address']}\n" if info else ""
    _mail_order(
        order, "Astra: Dein Server ist bereit",
        f"Hallo,\n\ndein Server '{order.instance_name}' wurde bereitgestellt und kann jetzt genutzt werden.\n"
        f"{address}Bestellung: {order.uuid}\n",
    )
    return True


def run_billing_tick(now: datetime | None = None) -> dict:
    """Setzt die Laufzeiten durch. Idempotent, gedacht fuer Cron/Compose alle paar Minuten.

    1. active und Laufzeit abgelaufen -> past_due, Instance suspendiert und gestoppt, Mail
    2. past_due laenger als BILLING_GRACE_DAYS -> Instance geloescht, expired, Mail
    3. Kuendigung zum Laufzeitende und Laufzeit abgelaufen -> sofort geloescht, expired
    4. Instance existiert nicht mehr -> expired ohne Runner-Aufruf

    Jede Bestellung wird einzeln committed; ein Fehler blockiert die anderen nicht (er wird gemeldet und
    die Bestellung im naechsten Tick erneut versucht).
    5. Erinnerungsmail `BILLING_REMINDER_DAYS` vor Laufzeitende (hoechstens einmal pro Order und Periode,
       nur bezahlte Bestellungen ohne Kuendigung)
    6. Kostenlose Bestellungen (price_cents = 0) werden bei Ablauf automatisch verlaengert
    7. Bezahlte Bestellungen ohne Instance (awaiting_provisioning) werden erneut bereitgestellt, sobald ein Node
       Platz hat (aelteste Zahlung zuerst, ohne Event bei jedem erfolglosen Versuch); die Laufzeit beginnt dann

    Rueckgabe: {"checked", "past_due", "expired", "reminded", "renewed", "provisioned", "errors": [{"order", "error"}]}
    """
    from flask import current_app
    now = _utc_naive(now) or _now()
    grace = timedelta(days=current_app.config.get("BILLING_GRACE_DAYS", 7))
    reminder = timedelta(days=current_app.config.get("BILLING_REMINDER_DAYS", 3))

    ids = [oid for (oid,) in db.session.query(Order.id)
           .filter(Order.status.in_((ORDER_ACTIVE, ORDER_PAST_DUE))).order_by(Order.id).all()]
    waiting = [oid for (oid,) in db.session.query(Order.id)
               .filter(Order.status == ORDER_AWAITING_PROVISIONING, Order.instance_id.is_(None))
               .order_by(Order.paid_at, Order.id).all()]
    summary = {"checked": len(ids) + len(waiting), "past_due": 0, "expired": 0, "reminded": 0, "renewed": 0,
               "provisioned": 0, "errors": []}
    for order_id in ids:
        try:
            outcome = _process_order(order_id, now, grace, reminder)
            if outcome:
                summary[outcome] += 1
        except Exception as e:
            db.session.rollback()
            order = db.session.get(Order, order_id)
            summary["errors"].append({"order": order.uuid if order else order_id, "error": f"{type(e).__name__}: {e}"})
            logger.exception("Billing-Tick: Bestellung %s fehlgeschlagen", order_id)

    for order_id in waiting:
        try:
            if _retry_provisioning(order_id, now):
                summary["provisioned"] += 1
        except Exception as e:
            db.session.rollback()
            order = db.session.get(Order, order_id)
            summary["errors"].append({"order": order.uuid if order else order_id, "error": f"{type(e).__name__}: {e}"})
            logger.exception("Billing-Tick: Bereitstellung der Bestellung %s fehlgeschlagen", order_id)

    logger.info("Billing-Tick: %s", summary)
    _record_tick(summary, now)
    return summary


# ── Zahlungsereignisse des Anbieters (M48) ──────────────

_FINAL_EVENT_STATES = ("processed", "ignored", "unapplied", "mismatch")


def process_payment_events(provider: str, events: list) -> list[dict]:
    """Verarbeitet Ereignisse eines Zahlungsanbieters idempotent.

    - Jede Event-ID wird nur einmal verarbeitet (Tabelle payment_events). Ein Ereignis, dessen Verarbeitung
      mit einem Fehler abbrach, bleibt `received` und wird bei der naechsten Zustellung erneut versucht.
    - `paid` verbucht die Zahlung wie mark-paid (Erstbereitstellung oder Verlaengerung), Referenz = Zahlungs-ID
    - Weicht Betrag oder Waehrung von der Bestellung ab, wird nichts freigeschaltet (`mismatch`)
    - Ist die Bestellung nicht mehr bezahlbar (storniert/beendet), bleibt das Geld unverbucht (`unapplied`)
      und es entsteht ein Activity-Event `order:payment_unapplied` (Erstattung pruefen)
    Rueckgabe: je Ereignis {"event_id", "status", "duplicate"}.
    """
    from sqlalchemy.exc import IntegrityError
    from app.domain.billing.models import PaymentEvent as PaymentEventRow

    results = []
    for ev in events:
        row = PaymentEventRow.query.filter_by(event_id=ev.event_id).first()
        if row is not None and row.status in _FINAL_EVENT_STATES:
            results.append({"event_id": ev.event_id, "status": row.status, "duplicate": True})
            continue
        if row is None:
            row = PaymentEventRow(event_id=ev.event_id, provider=provider, event_type=ev.type,
                                  order_uuid=ev.order_uuid, status="received")
            db.session.add(row)
            try:
                db.session.commit()
            except IntegrityError:  # paralleler Zustellversuch war schneller
                db.session.rollback()
                row = PaymentEventRow.query.filter_by(event_id=ev.event_id).first()
                if row is not None and row.status in _FINAL_EVENT_STATES:
                    results.append({"event_id": ev.event_id, "status": row.status, "duplicate": True})
                    continue

        status, detail = _apply_payment_event(ev)
        row = PaymentEventRow.query.filter_by(event_id=ev.event_id).first()
        row.status = status
        row.detail = detail
        row.processed_at = _now()
        db.session.commit()
        results.append({"event_id": ev.event_id, "status": status, "duplicate": False})
    return results


def _apply_payment_event(ev) -> tuple[str, str | None]:
    if ev.kind != "paid":
        return "ignored", None

    order = Order.query.filter_by(uuid=ev.order_uuid).first() if ev.order_uuid else None
    if order is None:
        logger.warning("Zahlung %s ohne passende Bestellung (order_uuid=%s)", ev.payment_reference, ev.order_uuid)
        return "ignored", f"Bestellung nicht gefunden (order_uuid={ev.order_uuid})"

    if ev.amount_cents != order.price_cents or (ev.currency or "").upper() != order.currency.upper():
        detail = (f"Betrag/Währung weichen ab: gezahlt {ev.amount_cents} {ev.currency}, "
                  f"erwartet {order.price_cents} {order.currency}")
        logger.error("Zahlung %s fuer Bestellung %s nicht verbucht: %s", ev.payment_reference, order.uuid, detail)
        _log("order:payment_unapplied", order, None, "Zahlung nicht verbucht: " + detail,
             {"reason": "mismatch", "payment_reference": ev.payment_reference})
        return "mismatch", detail

    if order.status not in (ORDER_PENDING_PAYMENT, ORDER_AWAITING_PROVISIONING, ORDER_ACTIVE, ORDER_PAST_DUE):
        detail = f"Bestellung ist '{order.status}', Zahlung {ev.payment_reference} konnte nicht verbucht werden"
        logger.error(detail)
        _log("order:payment_unapplied", order, None, detail,
             {"reason": f"order_{order.status}", "payment_reference": ev.payment_reference})
        return "unapplied", detail

    try:
        mark_order_paid(order, ev.payment_reference, None)
    except BillingError as e:
        if e.status_code != 409:
            raise
        # Zahlung ist verbucht, nur die Bereitstellung steht aus (awaiting_provisioning): kein Grund fuer Wiederholungen
        return "processed", f"bezahlt, Bereitstellung ausstehend: {e.message}"
    return "processed", None
