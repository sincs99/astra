"""M71 – Registrierungsschutz: Rate-Limits, Kontosperre, CAPTCHA (anbieterneutral), Honeypot."""

import os
import sys
import time as _time
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.infrastructure import mail
from app.domain.users.models import User
from app.config import ProductionConfig
from app.infrastructure import ratelimit
import requests

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
app.config["REGISTRATION_ENABLED"] = True
with app.app_context():
    db.create_all()
    for name in ("kunde", "zweiter"):
        u = User(username=name, email=f"{name}@example.com")
        u.set_password("passwort-1234")
        db.session.add(u)
    db.session.commit()
c = app.test_client()
NOW = [1_000_000.0]
clock = lambda: NOW[0]


def fresh():
    ratelimit.reset_memory()
    NOW[0] += 100000  # neues Zeitfenster


def post(path, body=None, ip="10.0.0.1", headers=None):
    return c.post(path, json=body or {}, environ_overrides={"REMOTE_ADDR": ip}, headers=headers or {})


def register(i, ip="10.0.0.1", **extra):
    return post("/api/auth/register", {"username": f"neu{i}", "email": f"neu{i}@example.com", "password": "geheim1234", **extra}, ip)


def login(login="kunde", password="passwort-1234", ip="10.0.0.1"):
    return post("/api/auth/login", {"login": login, "password": password}, ip)


def users():
    with app.app_context():
        return User.query.count()


print("Standard: im Testmodus aus")
check("RATELIMIT_ENABLED ist in der Testkonfiguration aus", app.config["RATELIMIT_ENABLED"] is False)
check("ohne Rate Limiting: 8 Registrierungen hintereinander", all(register(f"x{i}").status_code == 201 for i in range(8)))
app.config["RATELIMIT_ENABLED"] = True
with mock.patch.object(ratelimit.time, "time", clock):
    print("Registrierung: 5 pro Stunde je IP")
    fresh()
    rs = [register(i) for i in range(5)]
    check("5 Registrierungen ok", all(r.status_code == 201 for r in rs), str([r.status_code for r in rs]))
    n0 = users()
    r = register(5)
    check("6.: 429 mit error, code=rate_limited, retry_after_seconds", r.status_code == 429 and r.json["code"] == "rate_limited"
          and isinstance(r.json["retry_after_seconds"], int) and 1 <= r.json["retry_after_seconds"] <= 3600 and r.json["error"], str(r.json))
    check("Retry-After-Header passt zum Body", r.headers["Retry-After"] == str(r.json["retry_after_seconds"]))
    check("kein Konto angelegt", users() == n0)
    check("andere IP ist unabhaengig", register(6, ip="10.0.0.2").status_code == 201)
    NOW[0] += 1800
    r = register(7)
    check("nach 30 Minuten noch gesperrt, Restzeit ca. 30 Minuten", r.status_code == 429 and 1700 <= r.json["retry_after_seconds"] <= 1801, str(r.json))
    NOW[0] += 1801
    check("nach einer Stunde wieder erlaubt", register(8).status_code == 201)

    print("Login: 10 pro Minute je IP")
    fresh()
    rs = [login() for _ in range(10)]
    check("10 Logins ok", all(r.status_code == 200 for r in rs))
    r = login()
    check("11.: 429 rate_limited, Retry-After <= 60", r.status_code == 429 and r.json["code"] == "rate_limited" and 1 <= r.json["retry_after_seconds"] <= 60
          and r.headers["Retry-After"] == str(r.json["retry_after_seconds"]), str(r.json))
    check("andere IP kann sich anmelden", login(ip="10.0.0.9").status_code == 200)
    NOW[0] += 61
    check("nach 61 Sekunden wieder erlaubt", login().status_code == 200)

    print("Login: Fehlversuche je Konto (20 pro Stunde)")
    fresh()
    codes = [login(password="falsch", ip=f"10.1.0.{i}").status_code for i in range(20)]
    check("20 Fehlversuche von verschiedenen IPs: alle 401", codes == [401] * 20, str(codes))
    r = login(ip="10.1.0.99")
    check("21. Versuch mit RICHTIGEM Passwort: 429 (Konto gesperrt)", r.status_code == 429 and r.json["code"] == "rate_limited" and 1 <= r.json["retry_after_seconds"] <= 3600, str(r.json))
    check("Gross-/Kleinschreibung zaehlt gleich", login(login="KUNDE", ip="10.1.0.98").status_code == 429)
    check("anderes Konto bleibt nutzbar", login(login="zweiter", ip="10.1.0.97").status_code == 200)
    from app.domain.activity.models import ActivityLog
    with app.app_context():
        check("Activity-Event auth:login_blocked", ActivityLog.query.filter_by(event="auth:login_blocked").count() >= 2)
    NOW[0] += 3601
    check("nach einer Stunde wieder nutzbar", login(ip="10.1.0.96").status_code == 200)

    print("Erfolgreiche Logins zaehlen nicht als Fehlversuche")
    fresh()
    ok = [login(ip=f"10.2.0.{i}").status_code for i in range(25)]
    check("25 erfolgreiche Logins (verschiedene IPs) sperren das Konto nicht", ok == [200] * 25)

    print("Passwort-Reset-Anfrage: 3 pro Stunde je IP")
    fresh()
    rs = [post("/api/auth/password-reset/request", {"email": "kunde@example.com"}) for _ in range(3)]
    check("3 Anfragen ok", all(r.status_code == 200 for r in rs))
    r = post("/api/auth/password-reset/request", {"email": "kunde@example.com"})
    check("4.: 429 rate_limited", r.status_code == 429 and r.json["code"] == "rate_limited")
    check("andere IP ok", post("/api/auth/password-reset/request", {"email": "kunde@example.com"}, ip="10.0.0.3").status_code == 200)

    print("Uebrige Auth-Routen: RATELIMIT_AUTH_PER_MINUTE")
    fresh()
    rs = [post("/api/auth/verify-email", {"token": "x"}).status_code for _ in range(21)]
    check("20 pro Minute, die 21. ist 429", rs[:20] == [400] * 20 and rs[20] == 429, str(rs))

    print("Echte Client-IP hinter einem Proxy (ProxyFix)")
    from werkzeug.middleware.proxy_fix import ProxyFix
    fresh()
    for i in range(10):
        login(ip="172.16.0.1")  # Proxy-Adresse, ohne ProxyFix zaehlt nur sie
    r = login(ip="172.16.0.1", )
    check("ohne ProxyFix: X-Forwarded-For wird ignoriert (Spoofing wirkt nicht)", r.status_code == 429 and
          post("/api/auth/login", {"login": "kunde", "password": "passwort-1234"}, ip="172.16.0.1", headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 429)
    original = app.wsgi_app
    app.wsgi_app = ProxyFix(original, x_for=1)
    try:
        fresh()
        for _ in range(10):
            post("/api/auth/login", {"login": "kunde", "password": "passwort-1234"}, ip="172.16.0.1", headers={"X-Forwarded-For": "8.8.8.8"})
        a = post("/api/auth/login", {"login": "kunde", "password": "passwort-1234"}, ip="172.16.0.1", headers={"X-Forwarded-For": "8.8.8.8"})
        b = post("/api/auth/login", {"login": "kunde", "password": "passwort-1234"}, ip="172.16.0.1", headers={"X-Forwarded-For": "9.9.9.9"})
        spoof = post("/api/auth/login", {"login": "kunde", "password": "passwort-1234"}, ip="172.16.0.1", headers={"X-Forwarded-For": "1.1.1.1, 8.8.8.8"})
        check("mit ProxyFix(x_for=1): Limit gilt je echter Client-IP", a.status_code == 429 and b.status_code == 200)
        check("mit ProxyFix: vorgeschobene Adressen davor ändern den Schluessel nicht", spoof.status_code == 429)
    finally:
        app.wsgi_app = original

app.config["RATELIMIT_ENABLED"] = False

print("CAPTCHA: Konfiguration")
ratelimit.reset_memory()
r = c.get("/api/auth/captcha")
check("Standard none: provider none, site_key null", r.status_code == 200 and r.json == {"provider": "none", "site_key": None}, str(r.json))
app.config.update(CAPTCHA_PROVIDER="turnstile", CAPTCHA_SITE_KEY="0xSITE", CAPTCHA_SECRET="0xSECRET")
r = c.get("/api/auth/captcha")
check("turnstile: provider und site_key, nie das Secret", r.json == {"provider": "turnstile", "site_key": "0xSITE"} and "SECRET" not in r.get_data(as_text=True))
app.config.update(CAPTCHA_PROVIDER="unbekannt")
check("unbekannter Anbieter wird wie none ausgeliefert", c.get("/api/auth/captcha").json == {"provider": "none", "site_key": None})
check("... und verlangt kein Token", register("u1").status_code == 201)
app.config.update(CAPTCHA_PROVIDER="turnstile")


def fake(success=True, status=200, exc=None, bad_json=False):
    resp = mock.Mock(status_code=status)
    resp.json = (mock.Mock(side_effect=ValueError("kein json")) if bad_json else mock.Mock(return_value={"success": success}))
    return mock.Mock(side_effect=exc) if exc else mock.Mock(return_value=resp)


print("CAPTCHA: Registrierung")
with mock.patch("app.domain.accounts.captcha.requests.post", fake(True)) as post_mock:
    r = register("c1", captcha_token="tok-1")
    kw = post_mock.call_args.kwargs
    check("gueltig: 201, siteverify von Turnstile mit secret, response, remoteip, Timeout 5 s",
          r.status_code == 201 and post_mock.call_args.args[0] == "https://challenges.cloudflare.com/turnstile/v0/siteverify"
          and kw["data"] == {"secret": "0xSECRET", "response": "tok-1", "remoteip": "10.0.0.1"} and kw["timeout"] == 5, str(kw))
with mock.patch("app.domain.accounts.captcha.requests.post", fake(False)):
    n0 = users()
    r = register("c2", captcha_token="schlecht")
    check("ungueltig: 400 captcha_failed, kein Konto", r.status_code == 400 and r.json["code"] == "captcha_failed" and r.json["error"] and users() == n0, str(r.json))
with mock.patch("app.domain.accounts.captcha.requests.post", fake(True)) as post_mock:
    r = register("c3")
    check("Token fehlt: 400 captcha_failed ohne Netzaufruf", r.status_code == 400 and r.json["code"] == "captcha_failed" and not post_mock.called)
    r = register("c3", captcha_token="  ")
    check("leeres Token: 400 captcha_failed ohne Netzaufruf", r.status_code == 400 and not post_mock.called)
    r = register("c3", captcha_token=["x"])
    check("Token kein String: 400 captcha_failed", r.status_code == 400 and not post_mock.called)
for label, mk in [("Zeitueberschreitung", fake(exc=requests.Timeout("zu langsam"))), ("Verbindungsfehler", fake(exc=requests.ConnectionError("weg"))),
                  ("HTTP 502 des Dienstes", fake(status=502)), ("ungueltige Antwort", fake(bad_json=True))]:
    with mock.patch("app.domain.accounts.captcha.requests.post", mk):
        n0 = users()
        r = register("c4", captcha_token="tok")
        check(f"{label}: 503 captcha_unavailable, kein Konto", r.status_code == 503 and r.json["code"] == "captcha_unavailable" and users() == n0, str(r.json))
app.config.update(CAPTCHA_SECRET="")
with mock.patch("app.domain.accounts.captcha.requests.post", fake(True)) as post_mock:
    r = register("c5", captcha_token="tok")
    check("Secret fehlt: 503 captcha_unavailable ohne Netzaufruf", r.status_code == 503 and r.json["code"] == "captcha_unavailable" and not post_mock.called)
app.config.update(CAPTCHA_SECRET="0xSECRET", CAPTCHA_PROVIDER="hcaptcha", CAPTCHA_SITE_KEY="hsite")
check("hcaptcha: Site-Key im Endpunkt", c.get("/api/auth/captcha").json == {"provider": "hcaptcha", "site_key": "hsite"})
with mock.patch("app.domain.accounts.captcha.requests.post", fake(True)) as post_mock:
    r = register("c6", captcha_token="tok")
    check("hcaptcha: siteverify-URL von hCaptcha", r.status_code == 201 and post_mock.call_args.args[0] == "https://api.hcaptcha.com/siteverify")

print("CAPTCHA: Passwort-Reset-Anfrage")
from app.infrastructure import mail
mail.outbox.clear()
with mock.patch("app.domain.accounts.captcha.requests.post", fake(True)):
    r = post("/api/auth/password-reset/request", {"email": "kunde@example.com", "captcha_token": "tok"})
    check("gueltig: 200 und Mail", r.status_code == 200 and len(mail.outbox) == 1)
mail.outbox.clear()
with mock.patch("app.domain.accounts.captcha.requests.post", fake(False)):
    r = post("/api/auth/password-reset/request", {"email": "kunde@example.com", "captcha_token": "x"})
    check("ungueltig: 400 captcha_failed, keine Mail", r.status_code == 400 and r.json["code"] == "captcha_failed" and not mail.outbox)
r = post("/api/auth/password-reset/request", {"email": "kunde@example.com"})
check("ohne Token: 400 captcha_failed", r.status_code == 400 and r.json["code"] == "captcha_failed" and not mail.outbox)
with mock.patch("app.domain.accounts.captcha.requests.post", fake(exc=requests.Timeout("x"))):
    r = post("/api/auth/password-reset/request", {"email": "kunde@example.com", "captcha_token": "x"})
    check("Dienst nicht erreichbar: 503 captcha_unavailable", r.status_code == 503 and r.json["code"] == "captcha_unavailable")
app.config.update(CAPTCHA_PROVIDER="none")
check("ohne CAPTCHA geht die Anfrage wie bisher", post("/api/auth/password-reset/request", {"email": "kunde@example.com"}).status_code == 200)

print("Honeypot")
n0 = users()
r = register("h1", website="http://spam.example")
check("website gefuellt: 400 invalid_request, kein Konto", r.status_code == 400 and r.json["code"] == "invalid_request" and users() == n0, str(r.json))
check("leeres website-Feld ist unauffaellig", register("h2", website="").status_code == 201)
app.config.update(CAPTCHA_PROVIDER="turnstile")
with mock.patch("app.domain.accounts.captcha.requests.post", fake(True)) as post_mock:
    r = register("h3", website="x", captcha_token="tok")
    check("Honeypot wird vor dem CAPTCHA geprueft (kein Netzaufruf)", r.status_code == 400 and r.json["code"] == "invalid_request" and not post_mock.called)
app.config.update(CAPTCHA_PROVIDER="none")

print("Produktions-Pruefung")
mk = lambda **kw: type("C", (ProductionConfig,), kw)
check("unbekannter Anbieter: KRITISCH", any("CAPTCHA_PROVIDER" in i and "KRITISCH" in i for i in mk(CAPTCHA_PROVIDER="foo").validate_production()))
check("Anbieter ohne Keys: WARNUNG", any("CAPTCHA_PROVIDER=turnstile" in i and "WARNUNG" in i for i in mk(CAPTCHA_PROVIDER="turnstile", CAPTCHA_SITE_KEY="", CAPTCHA_SECRET="").validate_production()))
check("Anbieter mit Keys und none: keine Meldung", not any("CAPTCHA" in i for i in mk(CAPTCHA_PROVIDER="turnstile", CAPTCHA_SITE_KEY="a", CAPTCHA_SECRET="b").validate_production())
      and not any("CAPTCHA" in i for i in mk(CAPTCHA_PROVIDER="none").validate_production()))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
