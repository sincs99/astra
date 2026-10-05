"""Texte fuer Mails und Belege (M67). Schluessel gelten fuer alle Sprachen, Platzhalter ebenfalls.

Deutsch ist die Referenz und der Fallback. Admin-Alerts bleiben bewusst deutsch (nicht hier).
"""

MESSAGES: dict[str, dict[str, str]] = {
    "de": {
        # ── Konto ──
        "mail.verify.subject": "Astra: E-Mail-Adresse bestätigen",
        "mail.verify.body": (
            "Hallo {username},\n\nbitte bestätige deine E-Mail-Adresse (gültig {hours} Stunden):\n{link}\n\n"
            "Falls du dich nicht registriert hast, ignoriere diese Mail.\n"
        ),
        "mail.password_reset.subject": "Astra: Passwort zurücksetzen",
        "mail.password_reset.body": (
            "Hallo {username},\n\nüber diesen Link kannst du dein Passwort zurücksetzen "
            "(gültig {minutes} Minuten):\n{link}\n\nFalls du das nicht angefordert hast, ignoriere diese Mail.\n"
        ),
        "mail.recovery_used.subject": "Astra: Recovery-Code verwendet",
        "mail.recovery_used.body": (
            "Hallo,\n\nbei der Anmeldung für '{username}' wurde ein MFA-Recovery-Code verwendet. "
            "Es sind noch {remaining} Codes übrig.{warn}\nWarst du das nicht, ändere sofort dein Passwort.\n"
        ),
        "mail.recovery_used.warn": " Erzeuge bald neue Codes in den Kontoeinstellungen.",
        # ── Bestellungen ──
        "mail.payment_waiting.subject": "Astra: Zahlung eingegangen",
        "mail.payment_waiting.body": (
            "Hallo,\n\ndeine Zahlung für '{instance_name}' ist eingegangen. Aktuell ist auf unseren "
            "Servern kein Platz frei; dein Server wird automatisch bereitgestellt, sobald wieder Platz da ist. "
            "Die Laufzeit beginnt erst dann.\nBestellung: {uuid}\n"
        ),
        "mail.renewed.subject": "Astra: Zahlung eingegangen, Server verlängert",
        "mail.renewed.body": (
            "Hallo,\n\ndeine Zahlung ist eingegangen. Dein Server '{instance_name}' läuft jetzt bis "
            "{end}.\nBestellung: {uuid}\n"
        ),
        "mail.server_ready.subject": "Astra: Dein Server ist bereit",
        "mail.server_ready.body": (
            "Hallo,\n\n{intro} '{instance_name}' wurde bereitgestellt und kann jetzt genutzt werden.\n"
            "{address_block}Bestellung: {uuid}\n"
        ),
        "mail.server_ready.intro_paid": "deine Zahlung ist eingegangen und dein Server",
        "mail.server_ready.intro_plain": "dein Server",
        "mail.server_ready.address": "\nVerbindungsadresse: {address}\n",
        "mail.expired.subject": "Astra: Dein Server wurde beendet",
        "mail.expired.body": "Hallo,\n\ndein Server '{instance_name}' wurde beendet und gelöscht ({reason}).\nBestellung: {uuid}\n",
        "expire_reason.cancelled_at_period_end": "Kündigung zum Laufzeitende",
        "expire_reason.refunded": "Zahlung erstattet",
        "expire_reason.default": "Zahlung nicht eingegangen",
        "mail.past_due.subject": "Astra: Zahlung überfällig – dein Server wurde gesperrt",
        "mail.past_due.body": (
            "Hallo,\n\ndie Laufzeit deines Servers '{instance_name}' ist abgelaufen, der Server wurde gesperrt.\n"
            "Bitte begleiche die Zahlung innerhalb von {days} Tagen, sonst wird er gelöscht.\n"
            "Verwendungszweck: {purpose}\nBestellung: {uuid}\n"
        ),
        "mail.deletion_notice.subject": "Astra: Dein Server wird bald gelöscht",
        "mail.deletion_notice.body": (
            "Hallo,\n\nwegen deiner Kündigung wird dein Server '{instance_name}' am "
            "{end} gelöscht. Sichere vorher deine Dateien.\nBestellung: {uuid}\n"
        ),
        "mail.expiry_reminder.subject": "Astra: Die Laufzeit deines Servers endet bald",
        "mail.expiry_reminder.body": (
            "Hallo,\n\ndie Laufzeit deines Servers '{instance_name}' endet am {end}.\n"
            "Bitte veranlasse rechtzeitig die Zahlung ({price} für "
            "{period_days} Tage), sonst wird der Server gesperrt und nach der Karenzzeit gelöscht.\n"
            "Verwendungszweck: {purpose}\nBestellung: {uuid}\n"
        ),
        "mail.payment_open.subject": "Astra: Zahlung noch offen",
        "mail.payment_open.body": (
            "Hallo,\n\nfür deine Bestellung '{instance_name}' ist noch keine Zahlung eingegangen. "
            "Bitte überweise {price}; dein Server wird nach dem Zahlungseingang bereitgestellt.\n"
            "Verwendungszweck: {purpose}\nBestellung: {uuid}\n"
        ),
        "mail.refunded.subject": "Astra: Zahlung erstattet – dein Server wurde gesperrt",
        "mail.refunded.body": (
            "Hallo,\n\ndeine Zahlung wurde erstattet, daher wurde dein Server '{instance_name}' gesperrt. "
            "Er wird nach {days} Tagen gelöscht; sichere vorher deine Dateien oder melde dich beim Support.\n"
            "Bestellung: {uuid}\n"
        ),
        # ── Beleg ──
        "receipt.title_text": "ZAHLUNGSBELEG",
        "receipt.title": "Zahlungsbeleg",
        "receipt.number": "Belegnummer",
        "receipt.date": "Datum",
        "receipt.customer": "Kunde",
        "receipt.service": "Leistung",
        "receipt.service_value": "Gameserver-Paket {product}{blueprint}, Server '{instance_name}'",
        "receipt.term": "Laufzeit",
        "receipt.term_value": "{days} Tage",
        "receipt.amount": "Betrag",
        "receipt.purpose": "Verwendungszweck",
        "receipt.reference": "Zahlungsreferenz",
        "receipt.disclaimer": (
            "Dies ist ein Zahlungsbeleg und keine Rechnung im Sinne des Umsatzsteuergesetzes; "
            "er enthält keine Umsatzsteuerangaben."
        ),
        "invoice.title": "Rechnung",
        "invoice.title_text": "RECHNUNG",
        "invoice.number": "Rechnungsnummer",
        "credit.title": "Gutschrift / Stornorechnung",
        "credit.title_text": "GUTSCHRIFT / STORNORECHNUNG",
        "credit.number": "Gutschriftnummer",
        "receipt.credit_ref_label": "Bezug",
        "receipt.credit_ref": "zu Rechnung Nr. {number}",
        "receipt.period": "Leistungszeitraum",
        "receipt.period_after_setup": "{days} Tage ab Bereitstellung",
        "receipt.net": "Nettobetrag",
        "receipt.vat": "Umsatzsteuer {rate} %",
        "receipt.gross": "Bruttobetrag",
        "receipt.vat_id": "USt-IdNr.",
        "receipt.small_business_note": "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
    },
    "en": {
        "mail.verify.subject": "Astra: Confirm your email address",
        "mail.verify.body": (
            "Hello {username},\n\nplease confirm your email address (valid for {hours} hours):\n{link}\n\n"
            "If you did not register, please ignore this email.\n"
        ),
        "mail.password_reset.subject": "Astra: Reset your password",
        "mail.password_reset.body": (
            "Hello {username},\n\nuse this link to reset your password "
            "(valid for {minutes} minutes):\n{link}\n\nIf you did not request this, please ignore this email.\n"
        ),
        "mail.recovery_used.subject": "Astra: Recovery code used",
        "mail.recovery_used.body": (
            "Hello,\n\na two-factor recovery code was used to sign in to '{username}'. "
            "{remaining} codes are left.{warn}\nIf this was not you, change your password immediately.\n"
        ),
        "mail.recovery_used.warn": " Please generate new codes in your account settings soon.",
        "mail.payment_waiting.subject": "Astra: Payment received",
        "mail.payment_waiting.body": (
            "Hello,\n\nwe received your payment for '{instance_name}'. There is currently no free capacity on our "
            "servers; your server will be set up automatically as soon as capacity is available. "
            "The term only starts then.\nOrder: {uuid}\n"
        ),
        "mail.renewed.subject": "Astra: Payment received, server renewed",
        "mail.renewed.body": (
            "Hello,\n\nwe received your payment. Your server '{instance_name}' now runs until "
            "{end}.\nOrder: {uuid}\n"
        ),
        "mail.server_ready.subject": "Astra: Your server is ready",
        "mail.server_ready.body": (
            "Hello,\n\n{intro} '{instance_name}' has been set up and is ready to use.\n"
            "{address_block}Order: {uuid}\n"
        ),
        "mail.server_ready.intro_paid": "we received your payment and your server",
        "mail.server_ready.intro_plain": "your server",
        "mail.server_ready.address": "\nConnection address: {address}\n",
        "mail.expired.subject": "Astra: Your server has been terminated",
        "mail.expired.body": "Hello,\n\nyour server '{instance_name}' has been terminated and deleted ({reason}).\nOrder: {uuid}\n",
        "expire_reason.cancelled_at_period_end": "cancellation at the end of the term",
        "expire_reason.refunded": "payment refunded",
        "expire_reason.default": "payment not received",
        "mail.past_due.subject": "Astra: Payment overdue – your server has been suspended",
        "mail.past_due.body": (
            "Hello,\n\nthe term of your server '{instance_name}' has expired and the server has been suspended.\n"
            "Please pay within {days} days, otherwise it will be deleted.\n"
            "Payment reference: {purpose}\nOrder: {uuid}\n"
        ),
        "mail.deletion_notice.subject": "Astra: Your server will be deleted soon",
        "mail.deletion_notice.body": (
            "Hello,\n\nbecause you cancelled, your server '{instance_name}' will be deleted on "
            "{end}. Please back up your files first.\nOrder: {uuid}\n"
        ),
        "mail.expiry_reminder.subject": "Astra: The term of your server ends soon",
        "mail.expiry_reminder.body": (
            "Hello,\n\nthe term of your server '{instance_name}' ends on {end}.\n"
            "Please arrange payment in time ({price} for "
            "{period_days} days), otherwise the server will be suspended and deleted after the grace period.\n"
            "Payment reference: {purpose}\nOrder: {uuid}\n"
        ),
        "mail.payment_open.subject": "Astra: Payment still outstanding",
        "mail.payment_open.body": (
            "Hello,\n\nwe have not received a payment for your order '{instance_name}' yet. "
            "Please transfer {price}; your server will be set up once the payment has arrived.\n"
            "Payment reference: {purpose}\nOrder: {uuid}\n"
        ),
        "mail.refunded.subject": "Astra: Payment refunded – your server has been suspended",
        "mail.refunded.body": (
            "Hello,\n\nyour payment was refunded, so your server '{instance_name}' has been suspended. "
            "It will be deleted after {days} days; please back up your files first or contact support.\n"
            "Order: {uuid}\n"
        ),
        "receipt.title_text": "PAYMENT RECEIPT",
        "receipt.title": "Payment receipt",
        "receipt.number": "Receipt number",
        "receipt.date": "Date",
        "receipt.customer": "Customer",
        "receipt.service": "Service",
        "receipt.service_value": "Game server plan {product}{blueprint}, server '{instance_name}'",
        "receipt.term": "Term",
        "receipt.term_value": "{days} days",
        "receipt.amount": "Amount",
        "receipt.purpose": "Payment reference",
        "receipt.reference": "Transaction reference",
        "receipt.disclaimer": (
            "This is a payment receipt, not an invoice for VAT purposes; "
            "it does not contain any VAT information."
        ),
        "invoice.title": "Invoice",
        "invoice.title_text": "INVOICE",
        "invoice.number": "Invoice number",
        "credit.title": "Credit note",
        "credit.title_text": "CREDIT NOTE",
        "credit.number": "Credit note number",
        "receipt.credit_ref_label": "Reference",
        "receipt.credit_ref": "for invoice no. {number}",
        "receipt.period": "Service period",
        "receipt.period_after_setup": "{days} days from set-up",
        "receipt.net": "Net amount",
        "receipt.vat": "VAT {rate}%",
        "receipt.gross": "Gross amount",
        "receipt.vat_id": "VAT ID",
        "receipt.small_business_note": "No VAT is charged (small business exemption, section 19 of the German VAT Act).",
    },
}
