"""M72 – Kundenseitige API-Fehler einheitlich als {error, code} in der Sprache des Aufrufers (Accept-Language / users.locale)."""

import ast
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from unittest import mock

from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.users.models import User
from app.i18n import request_locale
from app.i18n import errors as err_catalog
from app.i18n.errors import ERRORS, STATUS_CODES, find, localize_error, placeholders
from app.infrastructure import ratelimit

passed = 0
failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  OK  {label}")
    else:
        failed += 1
        print(f"  FAIL {label}" + (f" – {detail}" if detail else ""))


app = create_app("testing")
with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    u1 = User(username="k1", email="k1@t.local")
    u2 = User(username="k2", email="k2@t.local")
    for u in (admin, u1, u2):
        u.set_password("passwort-1234")
    u2.locale = "en"
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=4096, disk_total=100000, cpu_total=400)
    db.session.add_all([admin, u1, u2, bp, agent])
    db.session.commit()
    for i in range(5):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, u1=u1.id, u2=u2.id, bp=bp.id, agent=agent.id)
    inst = Instance(name="srv", owner_id=ids["u2"], agent_id=ids["agent"], blueprint_id=ids["bp"], memory=256, disk=500, cpu=50, status="running")
    db.session.add(inst)
    db.session.commit()
    inst_uuid = inst.uuid

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
U1 = {"X-User-Id": str(ids["u1"])}   # Sprache nicht gesetzt = Deutsch
U2 = {"X-User-Id": str(ids["u2"])}   # users.locale = en
EN = {"Accept-Language": "en"}


def j(r):
    return r.get_json(silent=True) or {}


print("Katalog")
check("Platzhalter in DE und EN gleich", all(placeholders(d) == placeholders(e) for _, d, e in ERRORS), str([(co, d) for co, d, e in ERRORS if placeholders(d) != placeholders(e)]))
des = [d for _, d, _ in ERRORS]
check("deutsche Texte eindeutig", len(des) == len(set(des)))
check("Codes sind snake_case", all(re.fullmatch(r"[a-z][a-z0-9_]*", co) for co, _, _ in ERRORS))
check("jeder Eintrag wird ueber seinen eigenen (mit Beispielwerten gefuellten) Text gefunden",
      all(find(re.sub(r"\{\w+\}", "X", d)) is not None for _, d, _ in ERRORS))
check("... und liefert den eigenen Code, wenn kein anderer Eintrag dasselbe Muster belegt",
      all((find(re.sub(r"\{\w+\}", "X", d)) or ("?",))[0] == co for co, d, _ in ERRORS if not placeholders(d)))
check("EN-Texte sind uebersetzt (nicht leer)", all(e.strip() for _, _, e in ERRORS))

print("Katalog deckt alle kundenseitigen Fehlertexte im Quelltext ab")
FILES = ["app/api/auth/routes.py", "app/api/client/routes.py", "app/api/payments/routes.py", "app/domain/backups/service.py",
         "app/domain/auth/mfa_service.py", "app/domain/auth/apikey_service.py", "app/domain/ssh_keys/service.py", "app/domain/ssh_keys/validator.py",
         "app/domain/billing/service.py", "app/domain/billing/payments.py", "app/domain/routines/service.py", "app/domain/instances/service.py",
         "app/domain/collaborators/service.py", "app/domain/databases/service.py", "app/domain/accounts/service.py", "app/domain/auth/service.py",
         "app/infrastructure/ratelimit.py", "app/domain/accounts/captcha.py", "app/domain/agents/placement.py", "app/domain/routines/action_types.py"]
# nur Admin-Routen (Produktpflege, Zahlung bestaetigen, Erinnerung) oder interne Fehler: bleiben deutsch bzw. werden nie ausgeliefert
ADMIN_OR_INTERNAL = [
    r"^Field 'X' must be an integer$", r"^Field 'X' must be X$", r"^Kostenlose Produkte brauchen", r"^Produkt hat Bestellungen",
    r"^Bestellung im Status '.*' kann nicht als bezahlt markiert werden$", r"^Für eine Verlängerung ist 'payment_reference'",
    r"^Die Instance dieser Bestellung existiert nicht mehr", r"^Für eine Bestellung im Status '.*' gibt es nichts zu erinnern$",
    r"^Kostenlose Bestellung: nichts zu bezahlen$", r"^Bestellung ist gekündigt: es wird nichts mehr bezahlt$", r"^Der Kunde hat keine E-Mail-Adresse$",
    r"^Es wurde bereits vor kurzem manuell erinnert$", r"^current_period_end fehlt$", r"^Required fields missing: X$", r"^Field 'name' must be a non-empty string \(max 120 chars\)$",
    r"^Field 'description' must be a string$", r"^Blueprint X nicht gefunden$", r"^Field 'currency' must be a 3-letter ISO code$", r"^Field 'is_active' must be a boolean$",
    r"^Runner ist nicht initialisiert\. Bitte set_runner\(\) aufrufen\.$",
    # M80: Endpoint-Verwaltung ist Admin-API
    r"^Endpoints können im Status 'X' nicht geändert werden$", r"^Field 'endpoint_id' must be an integer$", r"^Endpoint X gehört nicht zum Agent der Instance$",
    r"^Endpoint X ist dieser Instance nicht zugeordnet$", r"^Der primäre Endpoint kann nicht entfernt werden \(zuerst einen anderen zum primären machen\)$",
]
INTERNAL_TEXTS = ("X: X",)  # Zusammenfassung des Billing-Ticks (type(e).__name__: e), wird nie an Kunden ausgeliefert


def sample(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "X" for v in node.values)
    return None


missing = []
checked = 0
base = os.path.dirname(__file__)
for rel in FILES:
    src = open(os.path.join(base, rel)).read()
    for node in ast.walk(ast.parse(src)):
        cands = []
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.endswith("Error") and node.args:
            cands.append(node.args[0])
        elif isinstance(node, ast.Dict):
            cands += [v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant) and k.value == "error"]
        elif (isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple) and len(node.value.elts) == 2
              and isinstance(node.value.elts[0], ast.Constant) and node.value.elts[0].value is False):
            cands.append(node.value.elts[1])
        elif isinstance(node, ast.Return) and isinstance(node.value, ast.JoinedStr) and rel.endswith("placement.py"):
            cands.append(node.value)
        for cand in cands:
            text = sample(cand)
            if text is None:
                continue
            checked += 1
            if find(text) is None and not any(re.search(p, text) for p in ADMIN_OR_INTERNAL) and text not in INTERNAL_TEXTS:
                missing.append((rel, node.lineno, text))
check(f"{checked} Fehlertexte geprueft: jeder hat einen Katalogeintrag (oder ist Admin/intern)", not missing, str(missing))
check("es wurden viele Stellen gefunden (Test sucht wirklich)", checked > 150, str(checked))

print("localize_error")
check("bekannter Text: EN mit Platzhaltern und Code", localize_error("Bestellung im Status 'expired' kann nicht bezahlt werden", None, 409, "en") == ("An order with status 'expired' cannot be paid", "order_not_payable"))
check("DE bleibt wortgleich", localize_error("Bestellung nicht gefunden", None, 404, "de") == ("Bestellung nicht gefunden", "order_not_found"))
check("vorhandener Code bleibt", localize_error("Bestellung nicht gefunden", "mein_code", 404, "en") == ("Order not found", "mein_code"))
check("verschachtelter Text wird mituebersetzt", localize_error("Bestellung bezahlt, aber Instance konnte nicht angelegt werden: Agent 'n1' ist nicht aktiv", None, 409, "en")[0]
      == "Order paid, but the instance could not be created: Agent 'n1' is not active")
check("unbekannter Text bleibt, Code nach HTTP-Status", localize_error("Wings sagt nein", None, 502, "en") == ("Wings sagt nein", "bad_gateway")
      and localize_error("irgendwas", None, 418, "en")[1] == "error" and localize_error("x", None, 404, "de")[1] == "not_found")
check("unbekannte Sprache -> Deutsch", localize_error("Bestellung nicht gefunden", None, 404, "fr")[0] == "Bestellung nicht gefunden")
check("Muster: laengere feste Anteile gewinnen ('Instance ist suspendiert: Grund' vs 'Instance ist suspendiert')",
      localize_error("Instance ist suspendiert: Missbrauch", None, 409, "en")[0] == "Instance is suspended: Missbrauch"
      and localize_error("Instance ist suspendiert", None, 409, "en")[0] == "Instance is suspended")
check("STATUS_CODES deckt die ueblichen Statuswerte ab", all(s in STATUS_CODES for s in (400, 401, 403, 404, 409, 429, 500, 502, 503)))

print("request_locale")
def locale_for(headers, path="/api/auth/me"):
    with app.test_request_context(path, headers=headers):
        return request_locale()
check("ohne Anmeldung und ohne Header: de", locale_for({}) == "de")
check("Accept-Language en", locale_for(EN) == "en")
check("en-US,en;q=0.9,de;q=0.8 -> en", locale_for({"Accept-Language": "en-US,en;q=0.9,de;q=0.8"}) == "en")
check("de-DE,de;q=0.9,en;q=0.5 -> de", locale_for({"Accept-Language": "de-DE,de;q=0.9,en;q=0.5"}) == "de")
check("fr,en;q=0.5 -> en (erster passender nach q)", locale_for({"Accept-Language": "fr,en;q=0.5"}) == "en")
check("nur fr -> de", locale_for({"Accept-Language": "fr-FR,fr;q=0.9"}) == "de")
check("kaputter Header -> de", locale_for({"Accept-Language": ";;;q=abc"}) == "de")
check("angemeldeter Nutzer ohne locale -> de, auch bei Accept-Language en", locale_for({**U1, **EN}) == "de")
check("angemeldeter Nutzer mit locale en gewinnt gegen Accept-Language de", locale_for({**U2, "Accept-Language": "de"}) == "en")
check("ohne Request-Kontext: de", request_locale() == "de")

print("Auth ohne Anmeldung")
r = c.post("/api/auth/login", json={"login": "k1", "password": "falsch"})
check("Standard: Deutsch wie bisher, mit code", r.status_code == 401 and j(r) == {"error": "Ungültige Anmeldedaten", "code": "invalid_credentials"}, str(j(r)))
r = c.post("/api/auth/login", json={"login": "k1", "password": "falsch"}, headers=EN)
check("Accept-Language en: englischer Text, gleicher Code", j(r) == {"error": "Invalid credentials", "code": "invalid_credentials"}, str(j(r)))
r = c.post("/api/auth/login", json={"login": "k1"}, headers=EN)
check("Pflichtfelder (bisher englisch): 400 mit code", r.status_code == 400 and j(r)["code"] == "login_fields_required" and j(r)["error"] == "Fields 'login' and 'password' are required")
r = c.get("/api/auth/me", headers=EN)
check("/me ohne Anmeldung: Authentication required, unauthorized", r.status_code == 401 and j(r) == {"error": "Authentication required", "code": "unauthorized"}, str(j(r)))
r = c.get("/api/auth/me")
check("/me ohne Anmeldung auf Deutsch", j(r) == {"error": "Authentifizierung erforderlich", "code": "unauthorized"})
app.config["REGISTRATION_ENABLED"] = False
r = c.post("/api/auth/register", json={"username": "x", "email": "x@x.de", "password": "geheim1234"}, headers=EN)
check("Registrierung deaktiviert: 403 EN", r.status_code == 403 and j(r) == {"error": "Registration is disabled", "code": "registration_disabled"}, str(j(r)))
app.config["REGISTRATION_ENABLED"] = True
r = c.post("/api/auth/register", json={"username": "x", "email": "kein-email", "password": "geheim1234"}, headers=EN)
check("ungueltige E-Mail: EN", j(r) == {"error": "Invalid email address", "code": "invalid_email"}, str(j(r)))
r = c.post("/api/auth/register", json={"username": "x", "email": "x@x.de", "password": "kurz"}, headers=EN)
check("Passwort zu kurz: EN mit Platzhalter", j(r)["code"] == "password_too_short" and re.fullmatch(r"Password must be at least \d+ characters long", j(r)["error"]), str(j(r)))
r = c.post("/api/auth/register", json={"username": "k1", "email": "neu@x.de", "password": "geheim1234"}, headers=EN)
check("Benutzername vergeben: 409 EN", r.status_code == 409 and j(r) == {"error": "Username already taken", "code": "username_taken"})
r = c.post("/api/auth/register", json={"username": "x", "email": "x@x.de", "password": "geheim1234", "locale": "fr"}, headers=EN)
check("ungueltige locale (explizit): bleibt EN-uebersetzt, code invalid_locale", j(r)["code"] == "invalid_locale" and j(r)["error"].startswith("Invalid language"), str(j(r)))
r = c.post("/api/auth/verify-email", json={"token": "x"}, headers=EN)
check("verify-email mit ungueltigem Token: EN", j(r) == {"error": "Invalid confirmation link", "code": "invalid_verification_link"}, str(j(r)))
r = c.post("/api/auth/password-reset/confirm", json={"token": "x", "password": "geheim1234"}, headers=EN)
check("Reset-Link ungueltig: EN", j(r) == {"error": "Invalid reset link", "code": "invalid_reset_link"}, str(j(r)))
r = c.post("/api/auth/register", json={"username": "x", "email": "x@x.de", "password": "geheim1234", "website": "spam"}, headers=EN)
check("Honeypot: EN, code invalid_request", r.status_code == 400 and j(r) == {"error": "Invalid request", "code": "invalid_request"})
app.config.update(CAPTCHA_PROVIDER="turnstile", CAPTCHA_SITE_KEY="s", CAPTCHA_SECRET="k")
r = c.post("/api/auth/register", json={"username": "x", "email": "x@x.de", "password": "geheim1234"}, headers=EN)
check("CAPTCHA fehlt: EN, captcha_failed", j(r) == {"error": "Security check failed, please try again", "code": "captcha_failed"}, str(j(r)))
with mock.patch("app.domain.accounts.captcha.requests.post", side_effect=__import__("requests").Timeout("x")):
    r = c.post("/api/auth/register", json={"username": "x", "email": "x@x.de", "password": "geheim1234", "captcha_token": "t"}, headers=EN)
check("CAPTCHA-Dienst weg: 503 EN, captcha_unavailable", r.status_code == 503 and j(r)["code"] == "captcha_unavailable" and j(r)["error"].startswith("The security check"), str(j(r)))
app.config.update(CAPTCHA_PROVIDER="none")

print("Rate-Limit")
app.config["RATELIMIT_ENABLED"] = True
ratelimit.reset_memory()
for _ in range(10):
    c.post("/api/auth/login", json={"login": "k2", "password": "passwort-1234"})
r = c.post("/api/auth/login", json={"login": "k2", "password": "passwort-1234"}, headers=EN)
check("429 EN mit code rate_limited, retry_after_seconds und Retry-After", r.status_code == 429 and j(r)["code"] == "rate_limited" and j(r)["error"] == "Too many requests, please try again later"
      and j(r)["retry_after_seconds"] >= 1 and r.headers["Retry-After"] == str(j(r)["retry_after_seconds"]), str(j(r)))
r = c.post("/api/auth/login", json={"login": "k2", "password": "passwort-1234"})
check("429 DE wortgleich", j(r)["error"] == "Zu viele Anfragen, bitte später erneut versuchen" and j(r)["code"] == "rate_limited")
app.config["RATELIMIT_ENABLED"] = False
ratelimit.reset_memory()

print("Kundenrouten: Sprache aus users.locale und Accept-Language")
r = c.get("/api/client/orders/gibt-es-nicht", headers=U1)
check("U1 (de): Deutsch", j(r) == {"error": "Bestellung nicht gefunden", "code": "order_not_found"}, str(j(r)))
r = c.get("/api/client/orders/gibt-es-nicht", headers=U2)
check("U2 (users.locale en): Englisch", j(r) == {"error": "Order not found", "code": "order_not_found"}, str(j(r)))
r = c.get("/api/client/orders/gibt-es-nicht", headers={**U2, "Accept-Language": "de"})
check("users.locale gewinnt gegen Accept-Language de", j(r)["error"] == "Order not found")
r = c.get("/api/client/orders/gibt-es-nicht", headers={**U1, **EN})
check("Nutzer ohne locale: Standard de (Accept-Language wirkt nur ohne Anmeldung)", j(r)["error"] == "Bestellung nicht gefunden")
r = c.get("/api/client/instances/00000000-0000-0000-0000-000000000000", headers=U2)
check("Instance nicht gefunden: EN", r.status_code == 404 and j(r) == {"error": "Instance not found", "code": "instance_not_found"}, str(j(r)))
r = c.post(f"/api/client/instances/{inst_uuid}/power", json={}, headers=U2)
check("Pflichtfeld signal: EN", r.status_code == 400 and j(r) == {"error": "Field 'signal' is required", "code": "signal_required"}, str(j(r)))
r = c.post(f"/api/client/instances/{inst_uuid}/power", json={"signal": "boom"}, headers=U2)
check("ungueltiges Signal: EN mit Platzhalter", j(r)["code"] == "invalid_signal" and j(r)["error"].startswith("Invalid signal. Allowed: "), str(j(r)))
r = c.post(f"/api/client/instances/{inst_uuid}/power", json={"signal": "boom"}, headers=U1)
check("... DE wortgleich 'Erlaubt:'", j(r)["error"].startswith("Invalid signal. Erlaubt: "))
r = c.patch("/api/client/account/ssh-keys/999", json={"name": "x"}, headers=U2)
check("SSH-Key nicht gefunden: EN", r.status_code == 404 and j(r) == {"error": "SSH key not found", "code": "ssh_key_not_found"}, str(j(r)))
r = c.post("/api/client/account/ssh-keys", json={"name": "k", "public_key": "ssh-rsa"}, headers=U2)
check("SSH-Key-Format: EN", r.status_code == 400 and j(r) == {"error": "Invalid key format: expected type and key body", "code": "ssh_key_format"}, str(j(r)))
r = c.post("/api/client/account/ssh-keys", json={"name": "k", "public_key": "foo AAAA"}, headers=U2)
check("SSH-Key-Typ: EN mit Platzhaltern", j(r)["code"] == "ssh_key_type_unsupported" and j(r)["error"].startswith("Unsupported key type 'foo'. Supported: "), str(j(r)))
r = c.patch("/api/client/account", json={"locale": "xx"}, headers=U2)
check("PATCH account: ungueltige Sprache EN", r.status_code == 400 and j(r) == {"error": "Invalid language (allowed: de, en)", "code": "invalid_locale"})
r = c.patch("/api/client/account", json={"billing_name": "x" * 201}, headers=U2)
check("PATCH account: Name zu lang, code bleibt invalid_billing_name, EN", j(r)["code"] == "invalid_billing_name" and j(r)["error"] == "billing_name must not exceed 200 characters", str(j(r)))
r = c.patch("/api/client/account", json={"billing_name": 5}, headers=U1)
check("PATCH account: kein Text, DE", j(r) == {"error": "billing_name muss ein Text sein", "code": "invalid_billing_name"})
r = c.patch("/api/client/account", json={}, headers=U2)
check("PATCH account: nichts zu aendern, EN", j(r)["code"] == "nothing_to_change" and j(r)["error"].startswith("Nothing to change"))
r = c.post("/api/client/orders", json={"product_id": 99999}, headers=U2)
check("Bestellung: Produkt nicht gefunden EN", r.status_code == 404 and j(r) == {"error": "Product not found", "code": "product_not_found"}, str(j(r)))
r = c.post("/api/client/orders", json={"product_id": "x"}, headers=U2)
check("Bestellung: product_id kein Integer", j(r)["code"] == "product_id_integer")
r = c.post("/api/client/orders/gibt-es-nicht/checkout", headers=U2)
check("Checkout: Bestellung nicht gefunden EN", j(r)["error"] == "Order not found")
r = c.post("/api/client/orders/gibt-es-nicht/cancel", headers=U2)
check("Stornieren: Bestellung nicht gefunden EN", j(r)["error"] == "Order not found")
r = c.get("/api/client/orders/gibt-es-nicht/receipt?format=pdf", headers=U2)
check("Beleg: 404 EN (Bestellung unbekannt)", j(r) == {"error": "Order not found", "code": "order_not_found"})
r = c.post(f"/api/client/instances/{inst_uuid}/databases", json={}, headers=U2)
check("Datenbank: Pflichtfeld provider_id EN", j(r)["code"] == "provider_id_required" and j(r)["error"] == "Field 'provider_id' is required", str(j(r)))
r = c.post(f"/api/client/instances/{inst_uuid}/routines", json={}, headers={**U2, "Accept-Language": "de"})
check("Routine: Pflichtfeld name (Text war schon englisch; users.locale en gewinnt)", j(r) == {"error": "Field 'name' is required", "code": "name_required"}, str(j(r)))
r = c.patch(f"/api/client/instances/{inst_uuid}/routines/99999", json={"name": "x"}, headers=U2)
check("Routine nicht gefunden: EN", j(r) == {"error": "Routine not found", "code": "routine_not_found"}, str(j(r)))
r = c.post(f"/api/client/instances/{inst_uuid}/power", json={"signal": "start"}, headers=U1)
check("Fremde Instance: 404 'Instance not found' (EN) bzw. deutsch fuer U1", r.status_code == 404 and j(r)["code"] == "instance_not_found" and j(r)["error"] == "Instance nicht gefunden", str(j(r)))
r = c.post(f"/api/client/instances/{inst_uuid}/collaborators", json={"user_id": ids["u2"], "permissions": ["control.console"]}, headers=U2)
check("Owner als Collaborator: 400 EN, code", j(r) == {"error": "The owner cannot be added as a collaborator", "code": "owner_not_collaborator"} or j(r).get("code") in ("owner_not_collaborator", "bad_request"), str(j(r)))
r = c.post(f"/api/client/instances/{inst_uuid}/collaborators", json={"user_id": 99999, "permissions": ["control.console"]}, headers=U2)
check("Collaborator: unbekannter User mit ID, EN mit Platzhalter", j(r) == {"error": "User with ID 99999 not found", "code": "user_not_found_id"}, str(j(r)))
r = c.post(f"/api/client/instances/{inst_uuid}/collaborators", json={"user_id": ids["u1"], "permissions": ["gibt.es.nicht"]}, headers=U2)
check("Collaborator: ungueltige Permissions, EN", j(r)["code"] == "invalid_permissions" and j(r)["error"].startswith("Invalid permissions: "), str(j(r)))

print("Admin bleibt deutsch")
r = c.get("/api/admin/orders/gibt-es-nicht", headers={**AH, **EN})
check("Admin-Route mit Accept-Language en: deutscher Text, keine Codes erzwungen", r.status_code == 404 and j(r) == {"error": "Bestellung nicht gefunden"}, str(j(r)))
r = c.get("/api/admin/products/99999", headers={**AH, **EN})
check("Admin: Produkt nicht gefunden deutsch", "nicht gefunden" in j(r).get("error", ""), str(j(r)))

print("Einheitliches Format auf allen Kunden-Routen (ohne Anmeldung)")
bad = []
n_checked = 0
import re as _re
for rule in app.url_map.iter_rules():
    if not rule.rule.startswith(("/api/client/", "/api/auth/")):
        continue
    for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
        url = _re.sub(r"<[^>]*int:[^>]*>", "1", rule.rule)
        url = _re.sub(r"<[^>]*>", "00000000-0000-0000-0000-000000000000", url)
        resp = c.open(url, method=method, json={}, headers=EN)
        n_checked += 1
        if resp.status_code >= 400 and resp.mimetype == "application/json":
            body = resp.get_json(silent=True)
            if not (isinstance(body, dict) and isinstance(body.get("error"), str) and isinstance(body.get("code"), str) and body["code"]):
                bad.append((method, rule.rule, resp.status_code, body))
check(f"{n_checked} Routen/Methoden geprueft: jede JSON-Fehlerantwort hat {{error, code}}", not bad and n_checked >= 60, str(bad[:5]))
r = c.get("/api/client/instances", headers=EN)
check("ohne Anmeldung (Kundenroute): 401 EN mit code", r.status_code == 401 and j(r) == {"error": "Authentication required", "code": "unauthorized"}, str(j(r)))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
