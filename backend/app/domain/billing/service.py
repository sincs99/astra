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
    ORDER_PAST_DUE, ORDER_CANCELLED, ORDER_COUNTING_STATUSES,
)
from app.domain.blueprints.models import Blueprint
from app.domain.users.models import User

logger = logging.getLogger(__name__)

MAX_PENDING_ORDERS_PER_USER = 5
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class BillingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
        raise BillingError("Produkt hat Bestellungen und kann nicht geloescht werden – bitte deaktivieren", 409)
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


def fulfill_order(order: Order) -> Order:
    """Legt die Instance einer bezahlten Bestellung an (automatische Platzierung)."""
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
        _log("order:provision_failed", order, None, f"Instance konnte nicht angelegt werden: {e.message}",
             {"reason": e.message})
        raise BillingError(f"Bestellung bezahlt, aber Instance konnte nicht angelegt werden: {e.message}", 409)

    order.instance_id = instance.id
    order.status = ORDER_ACTIVE
    order.current_period_end = (order.paid_at or _now()) + timedelta(days=order.billing_period_days)
    db.session.commit()
    return order


def mark_order_paid(order: Order, payment_reference: str | None = None, actor_id: int | None = None) -> Order:
    """Zahlung bestaetigen und Instance bereitstellen. Idempotent bei bereits aktiven Bestellungen.

    Eine bezahlte Bestellung ohne Instance (awaiting_provisioning) wird erneut bereitgestellt,
    ohne die Zahlung ein zweites Mal zu verbuchen.
    """
    # Zeilensperre: zwei gleichzeitige "bezahlt"-Aufrufe duerfen nur eine Instance erzeugen (PostgreSQL)
    order = db.session.query(Order).filter_by(id=order.id).with_for_update().one()

    if order.status in (ORDER_ACTIVE, ORDER_PAST_DUE) and order.instance_id:
        return order
    if order.status not in (ORDER_PENDING_PAYMENT, ORDER_AWAITING_PROVISIONING):
        raise BillingError(f"Bestellung im Status '{order.status}' kann nicht als bezahlt markiert werden", 409)

    first_payment = order.status == ORDER_PENDING_PAYMENT
    if first_payment:
        order.paid_at = _now()
        order.payment_reference = (payment_reference or "")[:191] or None
        db.session.commit()
        _log("order:paid", order, actor_id, "Bestellung als bezahlt markiert",
             {"payment_reference": order.payment_reference})
    return fulfill_order(order)


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
            _log("order:cancelled", order, actor_id, "Kuendigung zum Laufzeitende vorgemerkt")
    elif order.status == ORDER_AWAITING_PROVISIONING:
        raise BillingError("Bezahlte Bestellung wird noch bereitgestellt – bitte den Support kontaktieren", 409)
    else:
        raise BillingError(f"Bestellung im Status '{order.status}' kann nicht storniert werden", 409)
    return order
