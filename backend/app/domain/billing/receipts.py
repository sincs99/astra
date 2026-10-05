"""Rechnungen und Gutschriften mit fortlaufender Nummer (M62, ab M70 mit Umsatzsteuer).

Ein Dokument pro verbuchter Zahlung (`kind=invoice`, nicht fuer kostenlose Pakete) und eines pro Erstattung
(`kind=credit_note`, negative Betraege, verweist auf die Rechnung). Die Nummer kommt aus einem Zaehler je Jahr
(`invoice_counters`): Zeilensperre auf PostgreSQL, Zaehler und Dokument werden in einer Transaktion
geschrieben, bei einem Fehler wird beides zurueckgerollt. Dadurch entsteht keine Luecke, solange
Dokumente nie geloescht werden.

Preise sind Bruttopreise (B2C): netto = brutto / (1 + Satz), USt = brutto - netto, kaufmaennisch auf Cent gerundet,
die Summe aus den gerundeten Teilen. Der Satz ist `VAT_RATE` (0 = Kleinunternehmer, dann Hinweis nach § 19 UStG).
Gedacht ist die Kleinbetragsrechnung nach § 33 UStDV (bis 250 Euro): Anbieter, Datum, Leistung, Bruttobetrag und Steuersatz
bzw. Steuerbefreiung; die Anschrift des Empfaengers wird nur gedruckt, wenn der Kunde sie hinterlegt hat. Eine rechtliche
Pruefung durch den Betreiber bleibt noetig. Dokumente aus der Zeit vor M70 (ohne Steuerfelder im Schnappschuss) werden
weiter als Zahlungsbeleg dargestellt.
"""

import html
import logging
import string
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import current_app

from app.extensions import db
from app.domain.billing.models import InvoiceCounter, Order, Receipt
from app.i18n import format_date, format_money, normalize_locale, site_name, tr
from app.utils.timeutil import iso_utc

logger = logging.getLogger(__name__)

DEFAULT_SMALL_BUSINESS_NOTE = "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."
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


# ── Umsatzsteuer ────────────────────────────────────────


def parse_vat_rate(value, strict: bool = False) -> Decimal:
    """Steuersatz in Prozent als Decimal. `strict` wirft ValueError bei Unsinn (Produktions-Check); sonst gilt dann 0 und es wird geloggt."""
    try:
        text = str(value if value is not None else "0").strip().replace(",", ".") or "0"
        rate = Decimal(text)
        if not rate.is_finite() or rate < 0 or rate >= 100:
            raise InvalidOperation
        return rate
    except InvalidOperation:
        if strict:
            raise ValueError(f"'{value}' ist kein Prozentsatz zwischen 0 und 100")
        logger.error("VAT_RATE '%s' ist ungueltig, es gilt 0 Prozent", value)
        return Decimal(0)


def vat_split(gross_cents: int, rate: Decimal) -> tuple[int, int]:
    """(netto, USt) in Cent aus dem Bruttobetrag; netto kaufmaennisch gerundet, USt = brutto - netto. Vorzeichen bleibt erhalten."""
    sign = -1 if gross_cents < 0 else 1
    gross = abs(gross_cents)
    net = int((Decimal(gross) / (1 + rate / 100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return sign * net, sign * (gross - net)


def _rate_number(rate: Decimal) -> float | int:
    rate = rate.normalize()
    return int(rate) if rate == rate.to_integral() else float(rate)


def _seller_snapshot() -> dict:
    lines = [ln.strip() for ln in (current_app.config.get("INVOICE_SELLER") or "").splitlines() if ln.strip()]
    return {"lines": lines, "vat_id": (current_app.config.get("INVOICE_SELLER_VAT_ID") or "").strip() or None}


def _country() -> str:
    """Land des Betreibers (M74): "DE" oder "CH", unbekannte Werte gelten als "DE"."""
    value = str(current_app.config.get("INVOICE_COUNTRY") or "DE").strip().upper()
    return value if value in ("DE", "CH") else "DE"


def _k(snap: dict, key: str) -> str:
    """Nachrichtenschluessel passend zum Land des Belegs (Altbestand ohne `country`: Deutschland)."""
    return f"{key}.ch" if snap.get("country") == "CH" else key


def _billing_snapshot(user) -> dict | None:
    name = (user.billing_name or "").strip() if user else ""
    address = (user.billing_address or "").strip() if user else ""
    return {"name": name or None, "address": address or None} if (name or address) else None


def _document_snapshot(order: Order, gross: int, period: tuple | None) -> dict:
    customer = order.user
    rate = parse_vat_rate(current_app.config.get("VAT_RATE", "0"))
    net, vat = vat_split(gross, rate)
    snap = {
        "product_name": (order.snapshot or {}).get("product_name"),
        "blueprint_name": order.blueprint_name,
        "payment_purpose": order.payment_purpose,
        "instance_name": order.instance_name,
        "billing_period_days": order.billing_period_days,
        "customer": {"username": customer.username if customer else None,
                     "email": customer.email if customer else None},
        "vat_rate": _rate_number(rate), "net_cents": net, "vat_cents": vat, "gross_cents": gross,
        "period_start": iso_utc(period[0]) if period and period[0] else None,
        "period_end": iso_utc(period[1]) if period and period[1] else None,
        "seller": _seller_snapshot(),
        "country": _country(),
    }
    brand = site_name()
    if brand != "Astra":  # M75: Markenname im Belegkopf (der Standard "Astra" bleibt wie bisher unsichtbar)
        snap["site_name"] = brand
    billing = _billing_snapshot(customer)
    if billing:
        snap["customer_billing"] = billing
    return snap


# ── Ausstellen ──────────────────────────────────────────


def _insert_document(order_id: int, kind: str, payment_reference: str | None, now: datetime, build) -> Receipt | None:
    """Nummer vergeben und Dokument schreiben (eine Transaktion, bis zu 3 Versuche). `build(order)` liefert
    (gross_cents, snapshot, references_id) oder None, wenn nichts auszustellen ist. Best effort: None bei Fehlern."""
    from sqlalchemy.exc import IntegrityError
    for attempt in range(3):
        try:
            existing = Receipt.query.filter_by(order_id=order_id, payment_reference=payment_reference).first()
            if existing is not None:
                return existing
            order = db.session.get(Order, order_id)
            built = build(order)
            if built is None:
                return None
            gross, snapshot, references_id = built
            year = now.year
            seq = _next_sequence(year)
            doc = Receipt(
                number=_number_format().format(year=year, seq=seq), order_id=order_id, payment_reference=payment_reference,
                kind=kind, references_id=references_id, amount_cents=gross, currency=order.currency, issued_at=now,
                snapshot=snapshot,
            )
            db.session.add(doc)
            db.session.commit()
            return doc
        except IntegrityError:
            db.session.rollback()  # paralleler Zaehler-Start oder Dokument: erneut versuchen
        except Exception:
            db.session.rollback()
            logger.exception("%s fuer Bestellung %s konnte nicht ausgestellt werden", kind, order_id)
            return None
    logger.error("%s fuer Bestellung %s: Nummernvergabe nach mehreren Versuchen fehlgeschlagen", kind, order_id)
    return None


def _naive_utc(now: datetime | None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    return now


def issue_receipt(order: Order, payment_reference: str | None, now: datetime | None = None,
                  period: tuple | None = None) -> Receipt | None:
    """Stellt die Rechnung fuer eine verbuchte Zahlung aus (idempotent je Zahlungsreferenz). Best effort: None bei Fehlern.

    `period` = (Beginn, Ende) des bezahlten Zeitraums (Leistungszeitraum); unbekannt (None), wenn die Bereitstellung noch
    wartet, dann steht auf der Rechnung "Laufzeit ab Bereitstellung". Kostenlose Bestellungen bekommen keine Rechnung.
    Ein Fehler hier darf die Zahlung nie blockieren; er wird geloggt (es wird keine Nummer verbraucht).
    """
    if order.price_cents <= 0:
        return None
    ref = (payment_reference or "").strip()[:191] or None
    gross = order.price_cents
    return _insert_document(order.id, "invoice", ref, _naive_utc(now),
                            lambda o: (gross, _document_snapshot(o, gross, period), None))


def issue_credit_note(order: Order, invoice: Receipt, refunded_total_cents: int, event_id: str,
                      now: datetime | None = None) -> Receipt | None:
    """Gutschrift zu einer Rechnung bei Erstattung (idempotent je Erstattungs-Ereignis). Best effort: None bei Fehlern.

    `refunded_total_cents` ist die gesamte bisher erstattete Summe der Zahlung (Stripe meldet sie kumuliert); die Gutschrift
    deckt nur den noch nicht gutgeschriebenen Rest (hoechstens bis zum Rechnungsbetrag) ab, negative Betraege.
    """
    ref = f"refund:{event_id}"[:191]
    invoice_id, order_id = invoice.id, order.id

    def build(o):
        inv = db.session.get(Receipt, invoice_id)
        credited = sum(-r.amount_cents for r in Receipt.query.filter_by(references_id=invoice_id, kind="credit_note").all())
        amount = min(int(refunded_total_cents), inv.amount_cents) - credited
        if amount <= 0:
            return None  # schon vollstaendig gutgeschrieben
        snap = _document_snapshot(o, -amount, None)
        old = inv.snapshot or {}
        # Steuersatz, Leistung und Zeitraum der Rechnung uebernehmen (nicht der aktuellen Konfiguration)
        rate = parse_vat_rate(old.get("vat_rate", current_app.config.get("VAT_RATE", "0")))
        net, vat = vat_split(-amount, rate)
        snap.update({"vat_rate": _rate_number(rate), "net_cents": net, "vat_cents": vat, "gross_cents": -amount,
                     "period_start": old.get("period_start"), "period_end": old.get("period_end"),
                     "references_number": inv.number})
        if old.get("seller"):
            snap["seller"] = old["seller"]
        snap.pop("site_name", None)
        if old.get("site_name"):
            snap["site_name"] = old["site_name"]  # Markenname der Rechnung (M75)
        snap["country"] = old.get("country") or "DE"  # Altbestand ohne Feld: wie die Rechnung (Deutschland)
        if old.get("customer_billing"):
            snap["customer_billing"] = old["customer_billing"]
        return -amount, snap, invoice_id

    return _insert_document(order_id, "credit_note", ref, _naive_utc(now), build)


# ── Darstellung ─────────────────────────────────────────


def _locale_of(receipt: Receipt) -> str | None:
    """Sprache des Kunden (users.locale), Standard Deutsch. Das Dokument wird beim Abruf in dieser Sprache gerendert."""
    order = db.session.get(Order, receipt.order_id)
    user = order.user if order else None
    return user.locale if user else None


def _footer_lines() -> list[str]:
    return [ln.strip() for ln in (current_app.config.get("RECEIPT_FOOTER") or "").splitlines() if ln.strip()]


def _legacy(snap: dict) -> bool:
    """Dokumente aus der Zeit vor M70 haben keine Steuerfelder und werden weiter als Zahlungsbeleg dargestellt."""
    return "vat_rate" not in snap


def _seller(snap: dict) -> tuple[list[str], str | None]:
    seller = snap.get("seller")
    if seller is None:  # Altbestand: aktuelle Konfiguration
        seller = _seller_snapshot()
    lines = list(seller.get("lines") or [])
    brand = snap.get("site_name")
    if brand and not (lines and lines[0].casefold() == brand.casefold()):
        lines.insert(0, brand)
    return lines, seller.get("vat_id")


def _rate_text(loc, rate) -> str:
    text = f"{rate:g}" if isinstance(rate, float) else str(rate)
    return text.replace(".", ",") if normalize_locale(loc) == "de" else text


def _small_business_note(loc, snap: dict) -> str:
    """Eigener Text (INVOICE_SMALL_BUSINESS_NOTE) in beiden Sprachen, sonst der landesuebliche Standard je Sprache
    (der alte deutsche Standardtext zaehlt wie "nicht gesetzt")."""
    note = current_app.config.get("INVOICE_SMALL_BUSINESS_NOTE") or DEFAULT_SMALL_BUSINESS_NOTE
    return tr(loc, _k(snap, "receipt.small_business_note")) if note == DEFAULT_SMALL_BUSINESS_NOTE else note


def _period_text(loc, snap: dict) -> str:
    start, end = snap.get("period_start"), snap.get("period_end")
    if start and end:
        a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
        return f"{format_date(loc, a)} – {format_date(loc, b)} (UTC)"
    return tr(loc, "receipt.period_after_setup", days=snap.get("billing_period_days"))


def _document(receipt: Receipt, loc) -> dict:
    """Aufbereitete Teile fuer Text und HTML: Titel, Kopfzeilen, Empfaenger, Zeilen, Hinweise."""
    snap = receipt.snapshot or {}
    cust = snap.get("customer") or {}
    credit = receipt.kind == "credit_note"
    legacy = _legacy(snap)
    customer = f"{cust.get('username') or '-'}" + (f" ({cust['email']})" if cust.get("email") else "")
    service = tr(loc, "receipt.service_value", product=snap.get("product_name") or "-",
                 blueprint=f" ({snap['blueprint_name']})" if snap.get("blueprint_name") else "",
                 instance_name=snap.get("instance_name") or "-")
    gross = receipt.amount_cents
    seller_lines, vat_id = _seller(snap)
    vat_id_label = tr(loc, _k(snap, "receipt.vat_id"))

    if legacy:
        title, title_text = tr(loc, "receipt.title"), tr(loc, "receipt.title_text")
        rows = [(tr(loc, "receipt.number"), receipt.number),
                (tr(loc, "receipt.date"), format_date(loc, receipt.issued_at) + " (UTC)"),
                (tr(loc, "receipt.customer"), customer), (tr(loc, "receipt.service"), service),
                (tr(loc, "receipt.term"), tr(loc, "receipt.term_value", days=snap.get("billing_period_days"))),
                (tr(loc, "receipt.amount"), format_money(loc, gross, receipt.currency))]
        notes = [tr(loc, "receipt.disclaimer")]
        recipient: list[str] = []
        vat_id = None
        seller_lines = _seller(snap)[0]
    else:
        kind = "credit" if credit else "invoice"
        title, title_text = tr(loc, f"{kind}.title"), tr(loc, f"{kind}.title_text")
        rate = snap.get("vat_rate") or 0
        rows = [(tr(loc, f"{kind}.number"), receipt.number),
                (tr(loc, "receipt.date"), format_date(loc, receipt.issued_at) + " (UTC)")]
        if credit and snap.get("references_number"):
            rows.append((tr(loc, "receipt.credit_ref_label"), tr(loc, "receipt.credit_ref", number=snap["references_number"])))
        rows += [(tr(loc, "receipt.customer"), customer), (tr(loc, "receipt.service"), service),
                 (tr(loc, "receipt.period"), _period_text(loc, snap))]
        if rate:
            rows += [(tr(loc, "receipt.net"), format_money(loc, snap.get("net_cents", gross), receipt.currency)),
                     (tr(loc, _k(snap, "receipt.vat"), rate=_rate_text(loc, rate)), format_money(loc, snap.get("vat_cents", 0), receipt.currency)),
                     (tr(loc, "receipt.gross"), format_money(loc, gross, receipt.currency))]
            notes = []
        else:
            rows.append((tr(loc, "receipt.amount"), format_money(loc, gross, receipt.currency)))
            notes = [_small_business_note(loc, snap)]
        billing = snap.get("customer_billing") or {}
        recipient = [ln.strip() for ln in ([billing.get("name") or ""] + (billing.get("address") or "").splitlines()) if ln.strip()]
    if snap.get("payment_purpose") and not credit:
        rows.append((tr(loc, "receipt.purpose"), snap["payment_purpose"]))
    if receipt.payment_reference and not (credit and str(receipt.payment_reference).startswith("refund:")):
        rows.append((tr(loc, "receipt.reference"), receipt.payment_reference))
    return {"title": title, "title_text": title_text, "rows": rows, "notes": notes, "recipient": recipient,
            "seller_lines": seller_lines, "vat_id": vat_id, "vat_id_label": vat_id_label}


def render_text(receipt: Receipt, locale: str | None = None) -> str:
    loc = locale or _locale_of(receipt)
    d = _document(receipt, loc)
    lines = list(d["seller_lines"])
    if d["vat_id"]:
        lines.append(f"{d['vat_id_label']}: {d['vat_id']}")
    lines += [""] if lines else []
    if d["recipient"]:
        lines += d["recipient"] + [""]
    lines += [d["title_text"], ""]
    lines += [f"{k}: {v}" for k, v in d["rows"]]
    lines += [""] + d["notes"] + _footer_lines()
    return "\n".join(lines) + "\n"


def render_html(receipt: Receipt, locale: str | None = None) -> str:
    """Eigenstaendige HTML-Seite. Alle Werte (auch Servername, Name und Anschrift des Kunden) sind escaped."""
    loc = locale or _locale_of(receipt)
    d = _document(receipt, loc)
    e = html.escape
    seller = "".join(f"<div>{e(ln)}</div>" for ln in d["seller_lines"])
    if d["vat_id"]:
        seller += f"<div>{e(d['vat_id_label'])}: {e(d['vat_id'])}</div>"
    recipient = ("<div style=\"margin:1rem 0\">" + "".join(f"<div>{e(ln)}</div>" for ln in d["recipient"]) + "</div>") if d["recipient"] else ""
    rows = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in d["rows"])
    notes = "".join(f"<p><small>{e(n)}</small></p>" for n in d["notes"])
    foot = "".join(f"<p>{e(ln)}</p>" for ln in _footer_lines())
    return (
        f"<!doctype html><html lang=\"{normalize_locale(loc)}\"><head><meta charset=\"utf-8\">"
        f"<title>{e(d['title'])} {e(receipt.number)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem;color:#111}"
        "table{border-collapse:collapse;width:100%}th{text-align:left;padding:.4rem .8rem .4rem 0;width:11rem;vertical-align:top}"
        "td{padding:.4rem 0}small,p{color:#444}</style></head><body>"
        f"<div>{seller}</div>{recipient}<h1>{e(d['title'])}</h1><table>{rows}</table>{notes}{foot}</body></html>"
    )
