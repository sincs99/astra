"""Produkte (Pakete) und Bestellungen (M44).

Ein Produkt legt Ressourcen, Blueprint und Preis fest. Eine Bestellung haelt einen
Schnappschuss davon (Preis, Waehrung, Laufzeit, Ressourcen), damit spaetere Produkt-
aenderungen bestehende Bestellungen nicht veraendern.
"""

import uuid as _uuid
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.utils.timeutil import iso_utc

# Bestell-Status
ORDER_PENDING_PAYMENT = "pending_payment"          # angelegt, noch nicht bezahlt
ORDER_AWAITING_PROVISIONING = "awaiting_provisioning"  # bezahlt, Instance konnte noch nicht angelegt werden
ORDER_ACTIVE = "active"                            # bezahlt, Instance laeuft
ORDER_PAST_DUE = "past_due"                        # Laufzeit abgelaufen, Instance suspendiert
ORDER_CANCELLED = "cancelled"                      # vom Kunden storniert
ORDER_EXPIRED = "expired"                          # beendet (Instance geloescht)
ORDER_REFUNDED = "refunded"                        # voll erstattet (oder Streit verloren), Instance gesperrt, Karenzzeit

ALL_ORDER_STATUSES = (
    ORDER_PENDING_PAYMENT, ORDER_AWAITING_PROVISIONING, ORDER_ACTIVE,
    ORDER_PAST_DUE, ORDER_CANCELLED, ORDER_EXPIRED, ORDER_REFUNDED,
)
# Bestellungen, die gegen max_instances_per_user zaehlen (belegen oder reservieren einen Platz)
ORDER_COUNTING_STATUSES = (
    ORDER_PENDING_PAYMENT, ORDER_AWAITING_PROVISIONING, ORDER_ACTIVE, ORDER_PAST_DUE, ORDER_REFUNDED,
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
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
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
    # M59: voll erstattet (Beginn der Karenzzeit ist past_due_at) bzw. Zahlungsstreit offen
    refunded_at = db.Column(db.DateTime, nullable=True)
    disputed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    user = db.relationship("User", lazy=True)
    product = db.relationship("Product", lazy=True)
    instance = db.relationship("Instance", lazy=True)
    receipts = db.relationship("Receipt", lazy="selectin", order_by="Receipt.id", viewonly=True)

    def scheduled_deletion_at(self):
        """Zeitpunkt, zu dem der Server geloescht wird (None, wenn nichts ansteht)."""
        if self.status == ORDER_ACTIVE and self.cancel_at_period_end:
            return self.current_period_end
        if self.status == ORDER_REFUNDED and self.past_due_at:
            from flask import current_app
            return self.past_due_at + timedelta(days=current_app.config.get("BILLING_GRACE_DAYS", 7))
        if self.status == ORDER_PAST_DUE:
            if self.cancel_at_period_end:
                return self.current_period_end
            if self.past_due_at:
                from flask import current_app
                days = current_app.config.get("BILLING_GRACE_DAYS", 7)
                return self.past_due_at + timedelta(days=days)
        return None

    @property
    def payment_purpose(self) -> str | None:
        """Kurzer Verwendungszweck fuer die Ueberweisung (M64), z.B. "ASTRA-0042-7F".

        Laufende Nummer plus zwei Zeichen der UUID als Pruefzeichen: kurz genug fuer das
        Ueberweisungsformular, eindeutig genug, dass der Admin die Bestellung sicher zuordnet.
        None, solange die Bestellung noch keine ID hat.
        """
        if self.id is None or not self.uuid:
            return None
        return f"ASTRA-{self.id:04d}-{self.uuid.replace('-', '')[:2].upper()}"

    @property
    def blueprint_name(self) -> str | None:
        """Name der Spiel-Vorlage (M64): aus dem Produkt, sonst aus dem Schnappschuss."""
        product = self.product
        if product is not None and product.blueprint is not None:
            return product.blueprint.name
        bp_id = (self.snapshot or {}).get("blueprint_id")
        if bp_id is None:
            return None
        from app.domain.blueprints.models import Blueprint
        bp = db.session.get(Blueprint, bp_id)
        return bp.name if bp else None

    def to_dict(self, include_user: bool = False) -> dict:
        inst = self.instance
        deletion = self.scheduled_deletion_at()
        d = {
            "id": self.id,
            "uuid": self.uuid,
            "status": self.status,
            "product_id": self.product_id,
            "product_name": (self.snapshot or {}).get("product_name"),
            "blueprint_name": self.blueprint_name,
            "payment_purpose": self.payment_purpose,
            "instance_name": self.instance_name,
            "instance_uuid": inst.uuid if inst else None,
            "instance_status": inst.status if inst else None,
            "connection": inst.connection_info() if inst else None,
            "price_cents": self.price_cents,
            "currency": self.currency,
            "billing_period_days": self.billing_period_days,
            "resources": {k: (self.snapshot or {}).get(k) for k in ("memory", "swap", "disk", "io", "cpu")},
            "payment_reference": self.payment_reference,
            "paid_at": iso_utc(self.paid_at),
            "current_period_end": iso_utc(self.current_period_end),
            "cancel_at_period_end": bool(self.cancel_at_period_end),
            "past_due_at": iso_utc(self.past_due_at),
            "scheduled_deletion_at": iso_utc(deletion),
            "cancelled_at": iso_utc(self.cancelled_at),
            "refunded_at": iso_utc(self.refunded_at),
            "disputed": self.disputed_at is not None,
            "receipts": [r.to_summary() for r in self.receipts],
            "created_at": iso_utc(self.created_at),
        }
        if include_user:
            d["user_id"] = self.user_id
            d["username"] = self.user.username if self.user else None
        return d

    def __repr__(self):
        return f"<Order {self.uuid} {self.status}>"


class PaymentEvent(db.Model):
    """Eingegangene Ereignisse eines Zahlungsanbieters (Idempotenz und Nachvollziehbarkeit, M48)."""

    __tablename__ = "payment_events"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(255), unique=True, nullable=False)  # ID des Anbieters (Stripe: evt_...)
    provider = db.Column(db.String(32), nullable=False)
    event_type = db.Column(db.String(120), nullable=True)
    order_uuid = db.Column(db.String(36), nullable=True, index=True)
    # processed | ignored | unapplied (Geld da, Bestellung nicht mehr bezahlbar) | mismatch (Betrag/Waehrung weicht ab)
    status = db.Column(db.String(32), nullable=False, default="received")
    detail = db.Column(db.Text, nullable=True)
    # M68: Betrag laut Anbieter-Ereignis (Zahlung, bei Erstattungen der erstattete Betrag), NULL bei Altbestand
    # und bei Ereignissen ohne Betrag
    amount_cents = db.Column(db.Integer, nullable=True)
    currency = db.Column(db.String(3), nullable=True)
    received_at = db.Column(db.DateTime, default=_now)
    processed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "event_id": self.event_id, "provider": self.provider,
            "event_type": self.event_type, "order_uuid": self.order_uuid, "status": self.status,
            "detail": self.detail,
            "amount_cents": self.amount_cents, "currency": self.currency,
            "received_at": iso_utc(self.received_at),
            "processed_at": iso_utc(self.processed_at),
        }


class InvoiceCounter(db.Model):
    """Fortlaufender Zaehler der Belegnummern je Jahr (M62). Die Vergabe sperrt die Zeile (PostgreSQL)."""
    __tablename__ = "invoice_counters"

    scope = db.Column(db.String(16), primary_key=True)  # Jahr, z.B. "2026"
    last_number = db.Column(db.Integer, nullable=False, default=0)


class Receipt(db.Model):
    """Zahlungsbeleg mit fortlaufender Nummer (M62). Pro verbuchter Zahlung hoechstens einer, wird nie geloescht."""
    __tablename__ = "receipts"
    __table_args__ = (db.UniqueConstraint("order_id", "payment_reference", name="uq_receipts_order_payment"),)

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(64), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    payment_reference = db.Column(db.String(191), nullable=True)  # Gutschrift: "refund:<Ereignis-ID>"
    # M70: "invoice" (Rechnung, ab M62 Beleg) oder "credit_note" (Gutschrift mit negativen Betraegen, verweist auf die Rechnung)
    kind = db.Column(db.String(16), nullable=False, default="invoice", server_default="invoice")
    references_id = db.Column(db.Integer, db.ForeignKey("receipts.id"), nullable=True)
    amount_cents = db.Column(db.Integer, nullable=False)  # Brutto, bei Gutschriften negativ
    currency = db.Column(db.String(3), nullable=False)
    issued_at = db.Column(db.DateTime, nullable=False, default=_now)  # naive UTC
    # Schnappschuss zum Zeitpunkt der Zahlung: product_name, instance_name, billing_period_days, customer
    snapshot = db.Column(db.JSON, nullable=False)

    references = db.relationship("Receipt", remote_side=[id], lazy="joined", join_depth=1)

    def to_summary(self) -> dict:
        return {"number": self.number, "kind": self.kind, "issued_at": iso_utc(self.issued_at),
                "amount_cents": self.amount_cents, "currency": self.currency}

    def to_dict(self) -> dict:
        snap = self.snapshot or {}
        return {
            **self.to_summary(), "payment_reference": self.payment_reference,
            "references_number": self.references.number if self.references else snap.get("references_number"),
            # Steuerfelder: bei Dokumenten vor M70 (ohne Angaben im Schnappschuss) null
            "vat_rate": snap.get("vat_rate"), "net_cents": snap.get("net_cents"), "vat_cents": snap.get("vat_cents"),
            "gross_cents": self.amount_cents, "period_start": snap.get("period_start"), "period_end": snap.get("period_end"),
            "customer_billing": snap.get("customer_billing"), "seller": snap.get("seller"),
            **{k: v for k, v in snap.items() if k not in ("vat_rate", "net_cents", "vat_cents", "gross_cents", "period_start",
                                                          "period_end", "customer_billing", "seller", "references_number")},
        }
