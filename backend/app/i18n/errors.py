"""Fehlertexte der Kunden-API in Deutsch und Englisch (M72).

Kundenseitige Fehlerantworten (`/api/auth/*`, `/api/client/*`) haben immer die Form `{error, code}`: `error` ist der Text in der Sprache
des Aufrufers (`app.i18n.request_locale()`), `code` ein stabiler, maschinenlesbarer Code. Die Texte entstehen weiterhin an den Stellen,
die den Fehler ausloesen, auf Deutsch (bzw. so, wie sie schon immer lauteten). Dieser Katalog ordnet jedem dieser Texte einen Code und
die englische Fassung zu; `localize_error` sucht den Eintrag ueber den deutschen Text (feste Texte exakt, Texte mit {platzhalter}
ueber ein Muster) und setzt die Werte der Platzhalter in die englische Fassung ein. Admin-Routen bleiben deutsch.

Neue kundenseitige Fehlertexte brauchen einen Eintrag hier: `test_m72.py` durchsucht den Quelltext danach und schlaegt sonst fehl.
Texte ohne Eintrag (z.B. Fehlermeldungen des Wings-Daemons) bleiben unveraendert und bekommen einen Code nach dem HTTP-Status.
"""

import re

# (Code, Deutsch = Text wie er im Code steht, Englisch). Platzhalter {name} muessen in beiden Sprachen gleich sein.
ERRORS: list[tuple[str, str, str]] = [
    # ── Anmeldung, Konto ──
    ("unauthorized", "Authentifizierung erforderlich", "Authentication required"),
    ("admin_required", "Admin-Berechtigung erforderlich", "Administrator permission required"),
    ("rate_limited", "Zu viele Anfragen, bitte später erneut versuchen", "Too many requests, please try again later"),
    ("request_body_required", "Request body is required", "Request body is required"),
    ("request_body_object", "Request body must be a JSON object", "Request body must be a JSON object"),
    ("login_fields_required", "Fields 'login' and 'password' are required", "Fields 'login' and 'password' are required"),
    ("invalid_credentials", "Ungültige Anmeldedaten", "Invalid credentials"),
    ("email_not_verified", "E-Mail-Adresse noch nicht bestätigt", "Email address not confirmed yet"),
    ("email_not_verified", "Bitte bestätige zuerst deine E-Mail-Adresse", "Please confirm your email address first"),
    ("invalid_mfa_code", "Ungültiger MFA-Code", "Invalid MFA code"),
    ("invalid_request", "Ungültige Anfrage", "Invalid request"),
    ("captcha_failed", "Sicherheitsprüfung fehlgeschlagen, bitte erneut versuchen", "Security check failed, please try again"),
    ("captcha_unavailable", "Die Sicherheitsprüfung ist gerade nicht erreichbar, bitte später erneut versuchen",
     "The security check is currently unavailable, please try again later"),
    ("code_required", "Field 'code' is required", "Field 'code' is required"),
    ("invalid_locale", "Ungültige Sprache (erlaubt: de, en)", "Invalid language (allowed: de, en)"),
    ("nothing_to_change", "Nichts zu ändern (erlaubt: locale, billing_name, billing_address)",
     "Nothing to change (allowed: locale, billing_name, billing_address)"),
    ("invalid_text_field", "{field} muss ein Text sein", "{field} must be a text"),
    ("text_field_too_long", "{field} darf höchstens {max_len} Zeichen lang sein", "{field} must not exceed {max_len} characters"),
    ("password_too_short", "Passwort muss mindestens {min_length} Zeichen lang sein", "Password must be at least {min_length} characters long"),
    ("registration_disabled", "Registrierung ist deaktiviert", "Registration is disabled"),
    ("username_email_required", "Felder 'username' und 'email' sind erforderlich", "Fields 'username' and 'email' are required"),
    ("invalid_email", "Ungültige E-Mail-Adresse", "Invalid email address"),
    ("username_taken", "Benutzername bereits vergeben", "Username already taken"),
    ("email_taken", "E-Mail bereits registriert", "Email already registered"),
    ("invalid_verification_link", "Ungültiger Bestätigungs-Link", "Invalid confirmation link"),
    ("verification_link_expired", "Bestätigungs-Link ist abgelaufen", "Confirmation link has expired"),
    ("wrong_current_password", "Aktuelles Passwort ist falsch", "Current password is incorrect"),
    ("password_unchanged", "Das neue Passwort muss sich vom aktuellen unterscheiden", "The new password must differ from the current one"),
    ("invalid_reset_link_used", "Ungültiger oder bereits verwendeter Reset-Link", "Invalid or already used reset link"),
    ("reset_link_expired", "Reset-Link ist abgelaufen", "Reset link has expired"),
    ("invalid_reset_link", "Ungültiger Reset-Link", "Invalid reset link"),
    # ── MFA, API-Keys, SSH-Keys ──
    ("mfa_not_enabled", "MFA ist nicht aktiviert", "MFA is not enabled"),
    ("mfa_already_enabled", "MFA ist bereits aktiviert", "MFA is already enabled"),
    ("mfa_setup_not_started", "MFA-Setup wurde nicht gestartet", "MFA setup has not been started"),
    ("invalid_verification_code", "Ungültiger Verifikationscode", "Invalid verification code"),
    ("invalid_password", "Passwort ist falsch", "Password is incorrect"),
    ("user_not_found", "User nicht gefunden", "User not found"),
    ("invalid_key_type", "key_type muss 'account' oder 'application' sein", "key_type must be 'account' or 'application'"),
    ("api_key_not_found", "API Key nicht gefunden", "API key not found"),
    ("ssh_key_not_found", "SSH-Key nicht gefunden", "SSH key not found"),
    ("name_required", "Field 'name' is required", "Field 'name' is required"),
    ("name_too_long", "'name' darf maximal 191 Zeichen haben", "'name' must not exceed 191 characters"),
    ("public_key_required", "Field 'public_key' is required", "Field 'public_key' is required"),
    ("ssh_key_duplicate", "Ein SSH-Key mit diesem Fingerprint existiert bereits: {name}", "An SSH key with this fingerprint already exists: {name}"),
    ("ssh_key_empty", "Public key darf nicht leer sein", "Public key must not be empty"),
    ("ssh_key_format", "Ungültiges Key-Format: Typ und Key-Body erwartet", "Invalid key format: expected type and key body"),
    ("ssh_key_type_unsupported", "Nicht unterstützter Key-Typ '{key_type}'. Unterstützt: {supported}",
     "Unsupported key type '{key_type}'. Supported: {supported}"),
    ("ssh_key_body_short", "Key-Body ist zu kurz", "Key body is too short"),
    ("ssh_key_truncated", "Unerwartetes Ende der Key-Daten", "Unexpected end of key data"),
    ("ssh_key_header_mismatch", "Key-Header '{expected}' stimmt nicht mit Key-Typ im Body '{actual}' überein",
     "Key header '{expected}' does not match the key type in the body '{actual}'"),
    ("ssh_key_base64", "Key-Body ist kein gültiges Base64", "Key body is not valid Base64"),
    ("ssh_key_binary", "Key-Body hat ungültiges Binärformat", "Key body has an invalid binary format"),
    # ── Instances ──
    ("instance_not_found", "Instance nicht gefunden", "Instance not found"),
    ("missing_permission", "Fehlende Berechtigung: {permission}", "Missing permission: {permission}"),
    ("instance_suspended", "Instance ist suspendiert: {reason}", "Instance is suspended: {reason}"),
    ("instance_suspended", "Instance ist suspendiert", "Instance is suspended"),
    ("signal_required", "Field 'signal' is required", "Field 'signal' is required"),
    ("invalid_signal", "Invalid signal. Erlaubt: {allowed}", "Invalid signal. Allowed: {allowed}"),
    ("confirm_missing", "Bestätigung fehlt: 'confirm' muss dem Namen der Instance entsprechen", "Confirmation missing: 'confirm' must match the instance name"),
    ("no_valid_fields", "Keine gültigen Felder angegeben", "No valid fields provided"),
    ("agent_not_found", "Agent nicht gefunden", "Agent not found"),
    ("resources_unavailable", "Resources nicht abrufbar: {detail}", "Resources unavailable: {detail}"),
    ("user_not_found_id", "User mit ID {id} nicht gefunden", "User with ID {id} not found"),
    ("agent_not_found_id", "Agent mit ID {id} nicht gefunden", "Agent with ID {id} not found"),
    ("agent_inactive", "Agent '{name}' ist nicht aktiv", "Agent '{name}' is not active"),
    ("agent_maintenance", "Agent '{name}' befindet sich im Maintenance-Modus. Neue Deployments sind nicht möglich.",
     "Agent '{name}' is in maintenance mode. New deployments are not possible."),
    ("blueprint_not_found_id", "Blueprint mit ID {id} nicht gefunden", "Blueprint with ID {id} not found"),
    ("agent_capacity", "Agent '{name}' hat nicht genug freie Kapazitaet: {amount} {unit} angefragt, {free} frei",
     "Agent '{name}' does not have enough free capacity: {amount} {unit} requested, {free} free"),
    ("endpoint_requires_agent", "endpoint_id setzt eine explizite agent_id voraus", "endpoint_id requires an explicit agent_id"),
    ("no_agent_available", "Kein Agent mit freiem Endpoint und ausreichender Kapazität verfügbar", "No agent with a free endpoint and sufficient capacity available"),
    ("endpoint_not_found", "Endpoint mit ID {id} nicht gefunden", "Endpoint with ID {id} not found"),
    ("endpoint_wrong_agent", "Endpoint {endpoint_id} gehört nicht zu Agent {agent_id}", "Endpoint {endpoint_id} does not belong to agent {agent_id}"),
    ("endpoint_taken", "Endpoint {id} ist bereits belegt", "Endpoint {id} is already in use"),
    ("endpoint_blocked", "Endpoint {id} ist gesperrt", "Endpoint {id} is blocked"),
    ("no_free_endpoint", "Kein freier Endpoint auf Agent {id} verfügbar", "No free endpoint available on agent {id}"),
    ("power_action_failed", "Power-Aktion '{action}' fehlgeschlagen: {detail}", "Power action '{action}' failed: {detail}"),
    ("reinstall_not_possible", "Instance ist bereits im Status '{status}' – Reinstall nicht möglich", "Instance already has status '{status}' – reinstall not possible"),
    ("delete_not_possible", "Instance ist im Status '{status}' – Löschen nicht möglich (Admin kann mit force erzwingen)",
     "Instance has status '{status}' – deletion not possible (an admin can force it)"),
    ("transfer_same_agent", "Ziel-Agent ist derselbe wie der aktuelle Agent", "The target agent is the same as the current agent"),
    ("transfer_not_possible", "Instance ist im Status '{status}' – Transfer nicht möglich", "Instance has status '{status}' – transfer not possible"),
    ("target_agent_not_found", "Ziel-Agent {id} nicht gefunden", "Target agent {id} not found"),
    ("target_agent_inactive", "Ziel-Agent '{name}' ist nicht aktiv", "Target agent '{name}' is not active"),
    ("target_agent_maintenance", "Ziel-Agent '{name}' befindet sich im Maintenance-Modus", "Target agent '{name}' is in maintenance mode"),
    # ── Bestellungen, Zahlung ──
    ("order_not_found", "Bestellung nicht gefunden", "Order not found"),
    ("product_not_found", "Produkt nicht gefunden", "Product not found"),
    ("product_id_integer", "Field 'product_id' must be an integer", "Field 'product_id' must be an integer"),
    ("order_name_invalid", "Field 'name' must be a string (max 120 chars)", "Field 'name' must be a string (max 120 chars)"),
    ("too_many_pending_orders", "Zu viele offene Bestellungen ({max}) – bitte erst bezahlen oder stornieren",
     "Too many open orders ({max}) – please pay or cancel them first"),
    ("product_limit_reached", "Limit erreicht: maximal {max} Server dieses Pakets pro Kunde", "Limit reached: at most {max} servers of this plan per customer"),
    ("paid_but_not_provisioned", "Bestellung bezahlt, aber Instance konnte nicht angelegt werden: {reason}", "Order paid, but the instance could not be created: {reason}"),
    ("order_not_cancellable", "Bestellung im Status '{status}' kann nicht storniert werden", "An order with status '{status}' cannot be cancelled"),
    ("order_provisioning", "Bezahlte Bestellung wird noch bereitgestellt – bitte den Support kontaktieren", "The paid order is still being set up – please contact support"),
    ("order_not_payable", "Bestellung im Status '{status}' kann nicht bezahlt werden", "An order with status '{status}' cannot be paid"),
    ("receipt_format_invalid", "format muss html, text oder json sein", "format must be html, text or json"),
    ("no_receipt", "Für diese Bestellung gibt es keinen Beleg", "There is no receipt for this order"),
    ("manual", "Online-Zahlung ist nicht aktiviert. Bitte bezahle per Überweisung, wir schalten deine Bestellung nach Zahlungseingang frei.",
     "Online payment is not enabled. Please pay by bank transfer; we will activate your order once the payment arrives."),
    ("provider_disabled", "Zahlungsanbieter ist nicht aktiviert", "The payment provider is not enabled"),
    ("provider_unknown", "Unbekannter Zahlungsanbieter '{name}'", "Unknown payment provider '{name}'"),
    ("provider_not_configured", "Stripe ist nicht vollständig konfiguriert (STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET)",
     "Stripe is not fully configured (STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET)"),
    ("unsupported_currency", "Währung {currency} wird für Online-Zahlung nicht unterstützt", "Currency {currency} is not supported for online payment"),
    ("nothing_to_pay", "Für diese Bestellung ist nichts zu bezahlen", "There is nothing to pay for this order"),
    ("provider_error", "Zahlungsanbieter lieferte keine gültige Checkout-URL", "The payment provider did not return a valid checkout URL"),
    ("provider_unavailable", "Zahlungsanbieter ist gerade nicht erreichbar, bitte später erneut versuchen", "The payment provider is currently unavailable, please try again later"),
    ("stripe_inactive", "Stripe ist nicht der aktive Zahlungsanbieter", "Stripe is not the active payment provider"),
    ("signature_missing", "Signatur fehlt", "Signature missing"),
    ("invalid_payload", "Ungültige Nutzdaten", "Invalid payload"),
    ("invalid_signature", "Ungültige Signatur", "Invalid signature"),
    ("processing_failed", "Verarbeitung fehlgeschlagen", "Processing failed"),
    # ── Backups, Datenbanken, Mitarbeiter, Routinen ──
    ("backup_not_found", "Backup nicht gefunden", "Backup not found"),
    ("backup_not_restorable", "Nur erfolgreiche Backups können wiederhergestellt werden", "Only successful backups can be restored"),
    ("backup_locked", "Gesperrtes Backup kann nicht gelöscht werden", "A locked backup cannot be deleted"),
    ("database_not_found", "Datenbank nicht gefunden", "Database not found"),
    ("provider_id_required", "Field 'provider_id' is required", "Field 'provider_id' is required"),
    ("db_provider_not_found_id", "Provider mit ID {id} nicht gefunden", "Provider with ID {id} not found"),
    ("db_provider_not_found", "Provider nicht gefunden", "Provider not found"),
    ("host_required", "Field 'host' is required", "Field 'host' is required"),
    ("port_range", "Port must be between 1 and 65535", "Port must be between 1 and 65535"),
    ("max_databases_invalid", "max_databases must be >= 0 or null", "max_databases must be >= 0 or null"),
    ("provider_has_databases", "Provider hat noch {count} Datenbank(en) – zuerst löschen", "Provider still has {count} database(s) – delete them first"),
    ("provider_full", "Provider '{name}' hat max. Kapazität erreicht ({max})", "Provider '{name}' has reached its maximum capacity ({max})"),
    ("db_name_too_long", "db_name darf maximal 64 Zeichen haben", "db_name must not exceed 64 characters"),
    ("db_username_too_long", "username darf maximal 64 Zeichen haben", "username must not exceed 64 characters"),
    ("db_name_exists", "db_name '{name}' existiert bereits auf diesem Provider", "db_name '{name}' already exists on this provider"),
    ("db_username_exists", "username '{name}' existiert bereits auf diesem Provider", "username '{name}' already exists on this provider"),
    ("provisioning_failed", "Provisioning fehlgeschlagen: {detail}", "Provisioning failed: {detail}"),
    ("database_wrong_instance", "Datenbank gehört nicht zu dieser Instance", "The database does not belong to this instance"),
    ("password_rotation_failed", "Passwort-Rotation fehlgeschlagen: {detail}", "Password rotation failed: {detail}"),
    ("user_permissions_required", "Fields 'user_id' and 'permissions' are required", "Fields 'user_id' and 'permissions' are required"),
    ("permissions_required", "Field 'permissions' is required", "Field 'permissions' is required"),
    ("collaborator_not_found", "Collaborator nicht gefunden", "Collaborator not found"),
    ("owner_not_collaborator", "Owner kann nicht als Collaborator hinzugefügt werden", "The owner cannot be added as a collaborator"),
    ("already_collaborator", "User {id} ist bereits Collaborator dieser Instance", "User {id} is already a collaborator of this instance"),
    ("invalid_permissions", "Ungültige Permissions: {permissions}", "Invalid permissions: {permissions}"),
    ("routine_not_found", "Routine nicht gefunden", "Routine not found"),
    ("action_not_found", "Action nicht gefunden", "Action not found"),
    ("sequence_action_required", "Fields 'sequence' and 'action_type' are required", "Fields 'sequence' and 'action_type' are required"),
    ("invalid_action_type", "Ungültiger Action-Typ: {action_type}", "Invalid action type: {action_type}"),
    ("delay_negative", "delay_seconds muss >= 0 sein", "delay_seconds must be >= 0"),
    ("sequence_exists", "Sequence {sequence} existiert bereits in dieser Routine", "Sequence {sequence} already exists in this routine"),
    ("routine_running", "Routine wird bereits ausgeführt", "The routine is already running"),
    ("routine_empty", "Routine hat keine Actions", "The routine has no actions"),
    ("payload_required", "Payload ist erforderlich mit Feldern: {fields}", "Payload is required with fields: {fields}"),
    ("payload_missing_fields", "Fehlende Payload-Felder: {fields}", "Missing payload fields: {fields}"),
    ("invalid_power_signal", "Ungültiges Signal. Erlaubt: {allowed}", "Invalid signal. Allowed: {allowed}"),
    # ── Datei-Operationen (Eingabepruefung) ──
    ("path_query_required", "Query parameter 'path' is required", "Query parameter 'path' is required"),
    ("path_content_required", "Fields 'path' and 'content' are required", "Fields 'path' and 'content' are required"),
    ("path_required", "Field 'path' is required", "Field 'path' is required"),
    ("source_target_required", "Fields 'source' and 'target' are required", "Fields 'source' and 'target' are required"),
    ("files_destination_required", "Fields 'files' and 'destination' are required", "Fields 'files' and 'destination' are required"),
    ("files_list_required", "Field 'files' must be a non-empty list", "Field 'files' must be a non-empty list"),
    ("file_destination_required", "Fields 'file' and 'destination' are required", "Fields 'file' and 'destination' are required"),
]

# Fehlercode nach HTTP-Status, wenn weder die Antwort noch der Katalog einen Code liefern
STATUS_CODES = {
    400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed", 409: "conflict",
    413: "payload_too_large", 415: "unsupported_media_type", 422: "unprocessable", 429: "rate_limited", 500: "server_error",
    501: "not_implemented", 502: "bad_gateway", 503: "service_unavailable", 504: "gateway_timeout",
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_static: dict[str, tuple[str, str]] = {}
_patterns: list[tuple[re.Pattern, str, str, tuple[str, ...]]] = []


def placeholders(text: str) -> set[str]:
    return set(_PLACEHOLDER.findall(text))


def _build() -> None:
    if _static or _patterns:
        return
    dynamic = []
    for code, de, en in ERRORS:
        names = _PLACEHOLDER.findall(de)
        if not names:
            _static.setdefault(de, (code, en))
            continue
        regex, pos = "", 0
        for m in _PLACEHOLDER.finditer(de):
            regex += re.escape(de[pos:m.start()]) + f"(?P<{m.group(1)}>.+?)"
            pos = m.end()
        regex += re.escape(de[pos:])
        literal_len = len(_PLACEHOLDER.sub("", de))
        dynamic.append((literal_len, re.compile("^" + regex + "$", re.DOTALL), code, en, tuple(names)))
    dynamic.sort(key=lambda t: -t[0])  # spezifischere (laengere feste Anteile) zuerst
    _patterns.extend((rx, code, en, names) for _, rx, code, en, names in dynamic)


def find(message: str) -> tuple[str, str, dict] | None:
    """(Code, englische Vorlage, Werte der Platzhalter) zum deutschen Text oder None."""
    _build()
    hit = _static.get(message)
    if hit:
        return hit[0], hit[1], {}
    for rx, code, en, _names in _patterns:
        m = rx.match(message)
        if m:
            return code, en, m.groupdict()
    return None


def localize_error(message: str, code: str | None, status: int, locale: str, _depth: int = 0) -> tuple[str, str]:
    """Text in der gewuenschten Sprache und Code. Unbekannte Texte bleiben unveraendert (Code nach HTTP-Status)."""
    from app.i18n import normalize_locale
    found = find(message)
    if found is None:
        return message, code or STATUS_CODES.get(status, "error")
    found_code, en_template, values = found
    text = message
    if normalize_locale(locale) == "en":
        # Werte, die selbst ein bekannter Fehlertext sind (z.B. "...: {reason}"), ebenfalls uebersetzen
        if _depth < 2:
            values = {k: (localize_error(v, None, status, locale, _depth + 1)[0] if find(v) else v) for k, v in values.items()}
        text = en_template.format_map(_KeepMissing(values))
    return text, code or found_code


class _KeepMissing(dict):
    def __missing__(self, key):
        return "{" + key + "}"
