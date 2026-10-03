"""Webhooks der Zahlungsanbieter (M48). Ohne Login; die Echtheit sichert die Signaturpruefung."""

import logging

from flask import Blueprint, jsonify, request

from app.domain.billing.payments import PaymentError, get_provider
from app.domain.billing.service import process_payment_events

logger = logging.getLogger(__name__)

payments_bp = Blueprint("payments", __name__)


@payments_bp.route("/stripe", methods=["POST"])
def stripe_webhook():
    """Stripe-Webhook (checkout.session.completed u.a.).

    Antworten: 200 bei verarbeiteten, doppelten oder ignorierten Ereignissen; 400 bei fehlender oder
    ungueltiger Signatur; 404, wenn Stripe nicht der aktive Anbieter ist; 500 bei internen Fehlern
    (Stripe wiederholt die Zustellung dann).
    """
    try:
        provider = get_provider()
    except PaymentError as e:
        return jsonify({"error": e.message}), e.status_code
    if provider.name != "stripe":
        return jsonify({"error": "Stripe ist nicht der aktive Zahlungsanbieter"}), 404

    try:
        events = provider.handle_webhook(request.get_data(), request.headers.get("Stripe-Signature"))
    except PaymentError as e:
        return jsonify({"error": e.message}), e.status_code

    try:
        results = process_payment_events("stripe", events)
    except Exception:
        logger.exception("Stripe-Webhook: Verarbeitung fehlgeschlagen")
        return jsonify({"error": "Verarbeitung fehlgeschlagen"}), 500
    return jsonify({"received": True, "results": results})
