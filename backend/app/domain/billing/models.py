"""Produkte (Pakete) und Bestellungen (M44).

Ein Produkt legt Ressourcen, Blueprint und Preis fest. Eine Bestellung haelt einen
Schnappschuss davon (Preis, Waehrung, Laufzeit, Ressourcen), damit spaetere Produkt-
aenderungen bestehende Bestellungen nicht veraendern.
"""

import uuid as _uuid
from datetime import datetime, timedelta, timezone

from app.extensions import db

# Bestell-Status
ORDER_PENDING_PAYMENT = "pending_payment"          # angelegt, noch nicht bezahlt
ORDER_AWAITING_PROVISIONING = "awaiting_provisioning"  # bezahlt, Instance konnte noch nicht angelegt werden
ORDER_ACTIVE = "active"                            # bezahlt, Instance laeuft
ORDER_PAST_DUE = "past_due"                        # Laufzeit abgelaufen, Instance suspendiert
ORDER_CANCELLED = "cancelled"                      # vom Kunden storniert
ORDER_EXPIRED = "expired"                          # beendet (Instance geloescht)

ALL_ORDER_STATUSES = (
    ORDER_PENDING_PAYMENT, ORDER_AWAITING_PROVISIONING, ORDER_ACTIVE,
    ORDER_PAST_DUE, ORDER_CANCELLED, ORDER_EXPIRED,
)
# Bestellungen, die gegen max_instances_per_user zaehlen (belegen oder reservieren einen Platz)
ORDER_COUNTING_STATUSES = (
    ORDER_PENDING_PAYMENT, ORDER_AWAITING_PROVISIONING, ORDER_ACTIVE, ORDER_PAST_DUE,
)


def _now():
    """Naive UTC (die DateTime-Spalten sind ohne Zeitzone; vermeidet Serverzeitzonen-Effekte)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    blueprint_id = db.Column(db.Integer, db.ForeignKey("blueprints.id"), nullable=False)

    # Ressourcen der Instance (Einheiten wie bei Instance)
    memory = db.Column(db.Integer, nullable=False)   # MB
    swap = db.Column(db.Integer, nullable=False, default=0)
    disk = db.Column(db.Integer, nullable=False)     # MB
    io = db.Column(db.Integer, nullable=False, default=500)
    cpu = db.Column(db.Integer, nullable=False)      # %

    price_cents = db.Column(db.Integer, nullable=False, default=0)
    currency = db.Column(db.String(3), nullable=False, default="EUR")
    billing_period_days = db.Column(db.Integer, nullable=False, default=30)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # Begrenzung pro Kunde (None = unbegrenzt); bei kostenlosen Produkten Pflicht
    max_instances_per_user = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    blueprint = db.relationship("Blueprint", lazy=True)

    def resources(self) -> dict:
        return {"memory": self.memory, "swap": self.swap, "disk": self.disk,
                "io": self.io, "cpu": self.cpu}

    def to_public_dict(self) -> dict:
        """Fuer den Shop: keine internen Felder (Blueprint, Limits)."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "blueprint_name": self.blueprint.name if self.blueprint else None,
            "price_cents": self.price_cents,
            "currency": self.currency,
            "billing_period_days": self.billing_period_days,
            "resources": self.resources(),
        }

    def to_dict(self) -> dict:
        d = self.to_public_dict()
        d.update({
            "blueprint_id": self.blueprint_id,
            "is_active": self.is_active,
            "max_instances_per_user": self.max_instances_per_user,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        })
        return d

    def __repr__(self):
        return f"<Product {self.name}>"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(_uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    instance_id = db.Column(db.Integer, db.ForeignKey("instances.id"), nullable=True)
    status = db.Column(db.String(32), nullable=False, default=ORDER_PENDING_PAYMENT, index=True)

    # Name der zu erstellenden Instance (vom Kunden gewaehlt oder generiert)
    instance_name = db.Column(db.String(120), nullable=False)

    # Schnappschuss zum Bestellzeitpunkt
    price_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    billing_period_days = db.Column(db.Integer, nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)  # {product_name, blueprint_id, memory, swap, disk, io, cpu}

    payment_reference = db.Column(db.String(191), nullable=True)  # zuletzt verbuchte Zahlung
    # Alle verbuchten Zahlungsreferenzen: macht Verlaengerungen idempotent (kein doppeltes Verbuchen)
    payment_references = db.Column(db.JSON, nullable=True, default=list)
    paid_at = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, nullable=False, default=False)
    # Seit wann die Bestellung ueberfaellig ist (Beginn der Karenzzeit, M46)
    past_due_at = db.Column(db.DateTime, nullable=True)
    # Fuer welches Laufzeitende die Erinnerungsmail schon verschickt wurde (hoechstens eine pro Periode)
    reminded_for_period_end = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    user = db.relationship("User", lazy=True)
    product = db.relationship("Product", lazy=True)
    instance = db.relationship("Instance", lazy=True)

    def scheduled_deletion_at(self):
        """Zeitpunkt, zu dem der Server geloescht wird (None, wenn nichts ansteht)."""
        if self.status == ORDER_ACTIVE and self.cancel_at_period_end:
            return self.current_period_end
        if self.status == ORDER_PAST_DUE:
            if self.cancel_at_period_end:
                return self.current_period_end
            if self.past_due_at:
                from flask import current_app
                days = current_app.config.get("BILLING_GRACE_DAYS", 7)
                return self.past_due_at + timedelta(days=days)
        return None

    def to_dict(self, include_user: bool = False) -> dict:
        inst = self.instance
        deletion = self.scheduled_deletion_at()
        d = {
            "id": self.id,
            "uuid": self.uuid,
            "status": self.status,
            "product_id": self.product_id,
            "product_name": (self.snapshot or {}).get("product_name"),
            "instance_name": self.instance_name,
            "instance_uuid": inst.uuid if inst else None,
            "instance_status": inst.status if inst else None,
            "connection": inst.connection_info() if inst else None,
            "price_cents": self.price_cents,
            "currency": self.currency,
            "billing_period_days": self.billing_period_days,
            "resources": {k: (self.snapshot or {}).get(k) for k in ("memory", "swap", "disk", "io", "cpu")},
            "payment_reference": self.payment_reference,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "cancel_at_period_end": bool(self.cancel_at_period_end),
            "past_due_at": self.past_due_at.isoformat() if self.past_due_at else None,
            "scheduled_deletion_at": deletion.isoformat() if deletion else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_user:
            d["user_id"] = self.user_id
            d["username"] = self.user.username if self.user else None
        return d

    def __repr__(self):
        return f"<Order {self.uuid} {self.status}>"
