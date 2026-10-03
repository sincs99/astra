"""Zahlungsanbieter (M48).

Schnittstelle:
- create_checkout(order) -> URL, auf die der Kunde zum Bezahlen weitergeleitet wird
- handle_webhook(payload, signature) -> Liste von PaymentEvent (nach Signaturpruefung)

Implementierungen: ManualProvider (Standard, der Admin bestaetigt Zahlungen per mark-paid) und
StripeProvider (Stripe Checkout, mode=payment, plus Webhook). Der Anbieter wird ueber
PAYMENT_PROVIDER=manual|stripe gewaehlt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from flask import current_app

from app.domain.billing.models import Order

logger = logging.getLogger(__name__)

# Waehrungen ohne Nachkommastellen: price_cents waere dort kein Betrag in Cent, deshalb nicht unterstuetzt
_ZERO_DECIMAL = {"BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"}


class PaymentError(Exception):
    """Fehler eines Zahlungsvorgangs. `code` ist ein stabiler, maschinenlesbarer Fehlercode fuer das Frontend."""

    def __init__(self, message: str, status_code: int = 400, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


@dataclass
class PaymentEvent:
    """Ein fuer Astra relevantes Ereignis des Anbieters."""
    event_id: str
    type: str                       # Anbieter-Ereignistyp
    kind: str                       # "paid" | "ignored"
    order_uuid: str | None = None
    payment_reference: str | None = None
    amount_cents: int | None = None
    currency: str | None = None


class PaymentProvider:
    name = "base"
    supports_checkout = False

    def create_checkout(self, order: Order) -> str:
        raise NotImplementedError

    def handle_webhook(self, payload: bytes, signature: str | None) -> list[PaymentEvent]:
        raise NotImplementedError


class ManualProvider(PaymentProvider):
    """Heutiger Weg: Zahlung geht ausserhalb ein, der Admin bestaetigt sie per mark-paid."""

    name = "manual"
    supports_checkout = False

    def create_checkout(self, order: Order) -> str:
        raise PaymentError(
            "Online-Zahlung ist nicht aktiviert. Bitte bezahle per Ueberweisung, "
            "wir schalten deine Bestellung nach Zahlungseingang frei.", 409, "manual"
        )

    def handle_webhook(self, payload: bytes, signature: str | None) -> list[PaymentEvent]:
        raise PaymentError("Zahlungsanbieter ist nicht aktiviert", 404)


class StripeProvider(PaymentProvider):
    name = "stripe"
    supports_checkout = True

    def __init__(self, secret_key: str, webhook_secret: str, frontend_url: str):
        if not secret_key or not webhook_secret:
            raise PaymentError("Stripe ist nicht vollstaendig konfiguriert (STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET)", 500)
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.frontend_url = frontend_url.rstrip("/")

    def create_checkout(self, order: Order) -> str:
        import stripe

        currency = (order.currency or "").upper()
        if currency in _ZERO_DECIMAL:
            raise PaymentError(f"Waehrung {currency} wird fuer Online-Zahlung nicht unterstuetzt", 409, "unsupported_currency")
        if order.price_cents <= 0:
            raise PaymentError("Fuer diese Bestellung ist nichts zu bezahlen", 409, "nothing_to_pay")

        product_name = (order.snapshot or {}).get("product_name") or "Server"
        user = order.user
        try:
            session = stripe.checkout.Session.create(
                api_key=self.secret_key,
                mode="payment",
                client_reference_id=order.uuid,
                customer_email=user.email if user and user.email else None,
                line_items=[{
                    "quantity": 1,
                    "price_data": {
                        "currency": currency.lower(),
                        "unit_amount": order.price_cents,
                        "product_data": {
                            "name": f"{product_name} ({order.billing_period_days} Tage)",
                            "description": order.instance_name,
                        },
                    },
                }],
                # Beide Metadaten: an der Session und am PaymentIntent (fuer spaetere Erstattungen/Streitfaelle)
                metadata={"order_uuid": order.uuid},
                payment_intent_data={"metadata": {"order_uuid": order.uuid}},
                success_url=f"{self.frontend_url}/orders?paid={order.uuid}",
                cancel_url=f"{self.frontend_url}/orders?cancelled={order.uuid}",
            )
        except stripe.StripeError as e:
            logger.error("Stripe-Checkout fuer Bestellung %s fehlgeschlagen: %s", order.uuid, e)
            raise PaymentError("Zahlungsanbieter ist gerade nicht erreichbar, bitte spaeter erneut versuchen", 502,
                               "provider_unavailable")
        url = getattr(session, "url", None)
        # Nur https weiterreichen: der Kunde wird auf diese URL geleitet
        if not isinstance(url, str) or not url.startswith("https://"):
            logger.error("Stripe lieferte keine gueltige https-Checkout-URL fuer Bestellung %s", order.uuid)
            raise PaymentError("Zahlungsanbieter lieferte keine gueltige Checkout-URL", 502, "provider_error")
        return url

    def handle_webhook(self, payload: bytes, signature: str | None) -> list[PaymentEvent]:
        import stripe

        if not signature:
            raise PaymentError("Signatur fehlt", 400)
        try:
            event = stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
        except ValueError:
            raise PaymentError("Ungueltige Nutzdaten", 400)
        except stripe.SignatureVerificationError:
            logger.warning("Stripe-Webhook mit ungueltiger Signatur abgelehnt")
            raise PaymentError("Ungueltige Signatur", 400)

        # StripeObject ist je nach Bibliotheksversion kein dict mehr (kein .get): in normale Dicts umwandeln
        data = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        event_id, etype = data["id"], data["type"]
        obj = data["data"]["object"]

        if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            # Bei verzoegerten Zahlungsarten (z.B. SEPA-Lastschrift) ist "completed" noch nicht bezahlt
            if obj.get("payment_status") != "paid":
                return [PaymentEvent(event_id, etype, "ignored")]
            meta = obj.get("metadata") or {}
            return [PaymentEvent(
                event_id, etype, "paid",
                order_uuid=meta.get("order_uuid") or obj.get("client_reference_id"),
                payment_reference=obj.get("payment_intent") or obj.get("id"),
                amount_cents=obj.get("amount_total"),
                currency=(obj.get("currency") or "").upper() or None,
            )]
        return [PaymentEvent(event_id, etype, "ignored")]


def get_provider() -> PaymentProvider:
    """Der konfigurierte Zahlungsanbieter (PAYMENT_PROVIDER)."""
    cfg = current_app.config
    name = str(cfg.get("PAYMENT_PROVIDER", "manual")).strip().lower()
    if name == "manual":
        return ManualProvider()
    if name == "stripe":
        return StripeProvider(cfg.get("STRIPE_SECRET_KEY", ""), cfg.get("STRIPE_WEBHOOK_SECRET", ""),
                              cfg.get("FRONTEND_URL", "http://localhost:3000"))
    raise PaymentError(f"Unbekannter Zahlungsanbieter '{name}'", 500)
