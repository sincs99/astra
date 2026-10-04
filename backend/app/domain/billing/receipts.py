"""Zahlungsbelege mit fortlaufender Nummer (M62, Grundlage).

Ein Beleg pro verbuchter Zahlung (nicht fuer kostenlose Pakete). Die Nummer kommt aus einem Zaehler je Jahr
(`invoice_counters`): Zeilensperre auf PostgreSQL, Zaehler und Beleg werden in einer Transaktion
geschrieben, bei einem Fehler wird beides zurueckgerollt. Dadurch entsteht keine Luecke, solange
Belege nie geloescht werden. Es ist **kein Steuerbeleg**: keine Umsatzsteuer, keine Anschrift des Kunden.
"""

import html
import logging
import string
from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.domain.billing.models import InvoiceCounter, Order, Receipt
from app.i18n import format_date, format_money, normalize_locale, tr
from app.utils.timeutil import iso_utc

logger = logging.getLogger(__name__)

DEFAULT_NUMBER_FORMAT = "AST-{year}-{seq:05d}"
MAX_NUMBER_LENGTH = 64


def validate_number_format(fmt: str) -> str | None:
    """None, wenn das Format brauchbar ist, sonst eine Fehlerbeschreibung."""
    try:
        fields = [f for _, f, _, _ in string.Formatter().parse(fmt or "") if f is not None]
        if "seq" not in fields:
            return "{seq} fehlt (sonst waeren die Nummern nicht eindeutig)"
        if any(f not in ("year", "seq") for f in fields):
            return "erlaubt sind nur {year} und {seq}, z.B. AST-{year}-{seq:05d}"
        a, b = fmt.format(year=2026, seq=1), fmt.format(year=2026, seq=2)
        if a == b:
            return "{seq} wird nicht ausgegeben"
        if len(fmt.format(year=2026, seq=99999999)) > MAX_NUMBER_LENGTH:
            return f"Nummern dürfen höchstens {MAX_NUMBER_LENGTH} Zeichen lang sein"
    except (ValueError, KeyError, IndexError) as e:
        return f"{type(e).__name__}: {e}"
    return None


def _number_format() -> str:
    fmt = (current_app.config.get("INVOICE_NUMBER_FORMAT") or DEFAULT_NUMBER_FORMAT)
    if validate_number_format(fmt):
        logger.error("INVOICE_NUMBER_FORMAT '%s' ist ungueltig, es gilt das Standardformat", fmt)
        return DEFAULT_NUMBER_FORMAT
    return fmt


def _next_sequence(year: int) -> int:
    """Naechste laufende Nummer des Jahres. Muss in der Transaktion des Belegs laufen (Zeilensperre)."""
    counter = db.session.query(InvoiceCounter).filter_by(scope=str(year)).with_for_update().first()
    if counter is None:
        counter = InvoiceCounter(scope=str(year), last_number=0)
        db.session.add(counter)
        db.session.flush()  # paralleles Anlegen: IntegrityError, der Aufrufer wiederholt (keine Nummer verbraucht)
    counter.last_number += 1
    return counter.last_number


def issue_receipt(order: Order, payment_reference: str | None, now: datetime | None = None) -> Receipt | None:
    """Stellt den Beleg fuer eine verbuchte Zahlung aus (idempotent). Best effort: None bei Fehlern.

    Kostenlose Bestellungen bekommen keinen Beleg. Ein Fehler hier darf die Zahlung nie blockieren;
    er wird geloggt (der Beleg fehlt dann, es wird keine Nummer verbraucht).
    """
    from sqlalchemy.exc import IntegrityError
    if order.price_cents <= 0:
        return None
    ref = (payment_reference or "").strip()[:191] or None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    order_id = order.id
    for attempt in range(3):
        try:
            existing = Receipt.query.filter_by(order_id=order_id, payment_reference=ref).first()
            if existing is not None:
                return existing
            order = db.session.get(Order, order_id)
            year = now.year
            seq = _next_sequence(year)
            customer = order.user
            receipt = Receipt(
                number=_number_format().format(year=year, seq=seq), order_id=order_id, payment_reference=ref,
                amount_cents=order.price_cents, currency=order.currency, issued_at=now,
                snapshot={
                    "product_name": (order.snapshot or {}).get("product_name"),
                    "blueprint_name": order.blueprint_name,
                    "payment_purpose": order.payment_purpose,
                    "instance_name": order.instance_name,
                    "billing_period_days": order.billing_period_days,
                    "customer": {"username": customer.username if customer else None,
                                 "email": customer.email if customer else None},
                },
            )
            db.session.add(receipt)
            db.session.commit()
            return receipt
        except IntegrityError:
            db.session.rollback()  # paralleler Zaehler-Start oder Beleg: erneut versuchen
        except Exception:
            db.session.rollback()
            logger.exception("Beleg fuer Bestellung %s konnte nicht ausgestellt werden", order_id)
            return None
    logger.error("Beleg fuer Bestellung %s: Nummernvergabe nach mehreren Versuchen fehlgeschlagen", order_id)
    return None


# ── Darstellung ─────────────────────────────────────────


def _locale_of(receipt: Receipt) -> str | None:
    """Sprache des Kunden (users.locale), Standard Deutsch. Der Beleg wird beim Abruf in dieser Sprache gerendert."""
    order = db.session.get(Order, receipt.order_id)
    user = order.user if order else None
    return user.locale if user else None


def _seller_lines() -> list[str]:
    return [ln.strip() for ln in (current_app.config.get("INVOICE_SELLER") or "").splitlines() if ln.strip()]


def _footer_lines() -> list[str]:
    return [ln.strip() for ln in (current_app.config.get("RECEIPT_FOOTER") or "").splitlines() if ln.strip()]


def _fields(receipt: Receipt, loc) -> list[tuple[str, str]]:
    snap = receipt.snapshot or {}
    cust = snap.get("customer") or {}
    rows = [
        (tr(loc, "receipt.number"), receipt.number),
        (tr(loc, "receipt.date"), format_date(loc, receipt.issued_at) + " (UTC)"),
        (tr(loc, "receipt.customer"), f"{cust.get('username') or '-'}" + (f" ({cust['email']})" if cust.get("email") else "")),
        (tr(loc, "receipt.service"), tr(
            loc, "receipt.service_value", product=snap.get("product_name") or "-",
            blueprint=f" ({snap['blueprint_name']})" if snap.get("blueprint_name") else "",
            instance_name=snap.get("instance_name") or "-")),
        (tr(loc, "receipt.term"), tr(loc, "receipt.term_value", days=snap.get("billing_period_days"))),
        (tr(loc, "receipt.amount"), format_money(loc, receipt.amount_cents, receipt.currency)),
    ]
    if snap.get("payment_purpose"):
        rows.append((tr(loc, "receipt.purpose"), snap["payment_purpose"]))
    if receipt.payment_reference:
        rows.append((tr(loc, "receipt.reference"), receipt.payment_reference))
    return rows


def render_text(receipt: Receipt, locale: str | None = None) -> str:
    loc = locale or _locale_of(receipt)
    lines = _seller_lines() + ([""] if _seller_lines() else [])
    lines.append(tr(loc, "receipt.title_text"))
    lines.append("")
    lines += [f"{k}: {v}" for k, v in _fields(receipt, loc)]
    lines += ["", tr(loc, "receipt.disclaimer")] + _footer_lines()
    return "\n".join(lines) + "\n"


def render_html(receipt: Receipt, locale: str | None = None) -> str:
    """Eigenstaendige HTML-Seite. Alle Werte (auch der vom Kunden gewaehlte Servername) sind escaped."""
    loc = locale or _locale_of(receipt)
    e = html.escape
    seller = "".join(f"<div>{e(ln)}</div>" for ln in _seller_lines())
    rows = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in _fields(receipt, loc))
    foot = "".join(f"<p>{e(ln)}</p>" for ln in _footer_lines())
    title = tr(loc, "receipt.title")
    return (
        f"<!doctype html><html lang=\"{normalize_locale(loc)}\"><head><meta charset=\"utf-8\">"
        f"<title>{e(title)} {e(receipt.number)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem;color:#111}"
        "table{border-collapse:collapse;width:100%}th{text-align:left;padding:.4rem .8rem .4rem 0;width:11rem;vertical-align:top}"
        "td{padding:.4rem 0}small,p{color:#444}</style></head><body>"
        f"<div>{seller}</div><h1>{e(title)}</h1><table>{rows}</table>"
        f"<p><small>{e(tr(loc, 'receipt.disclaimer'))}</small></p>{foot}</body></html>"
    )
