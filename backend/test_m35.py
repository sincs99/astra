"""M35 – Admin-Guard fuer den gesamten /api/admin-Blueprint."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.users.models import User

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
app.config["ADMIN_GUARD_ENABLED"] = True

with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    admin.set_password("test1234")
    plain = User(username="usr", email="usr@t.local", is_admin=False)
    plain.set_password("test1234")
    db.session.add_all([admin, plain])
    db.session.commit()
    admin_id, plain_id = admin.id, plain.id

c = app.test_client()
protected = [
    ("get", "/api/admin/users"),
    ("post", "/api/admin/users"),
    ("get", "/api/admin/agents"),
    ("post", "/api/admin/agents"),
    ("get", "/api/admin/instances"),
    ("get", "/api/admin/blueprints"),
    ("get", "/api/admin/health/detailed"),
]

print("Ohne Authentifizierung")
r = c.get("/api/admin/health")
check("/health bleibt offen", r.status_code == 200)
for method, path in protected:
    r = getattr(c, method)(path, json={})
    check(f"{method.upper()} {path} -> 401", r.status_code == 401, str(r.status_code))
import re
rules = [r for r in app.url_map.iter_rules()
         if r.endpoint.startswith("admin.") and r.endpoint != "admin.health"]
bad = []
for rule in rules:
    path = re.sub(r"<[^>]+>", "1", rule.rule)
    for method in rule.methods - {"HEAD", "OPTIONS"}:
        code = c.open(path, method=method, json={}).status_code
        if code != 401:
            bad.append(f"{method} {rule.rule} -> {code}")
check(f"alle {len(rules)} Admin-Routen ohne Login -> 401", not bad, "; ".join(bad))

print("Normaler Nutzer")
h = {"X-User-Id": str(plain_id)}
for method, path in protected:
    r = getattr(c, method)(path, json={}, headers=h)
    check(f"{method.upper()} {path} -> 403", r.status_code == 403, str(r.status_code))

print("Admin")
h = {"X-User-Id": str(admin_id)}
r = c.get("/api/admin/users", headers=h)
check("Admin darf Users listen", r.status_code == 200)
r = c.get("/api/admin/health/detailed", headers=h)
check("Admin darf health/detailed", r.status_code in (200, 503), str(r.status_code))
tok = c.post("/api/auth/login", json={"login": "adm", "password": "test1234"}).json["access_token"]
r = c.get("/api/admin/users", headers={"Authorization": f"Bearer {tok}"})
check("Admin mit JWT", r.status_code == 200)
tok = c.post("/api/auth/login", json={"login": "usr", "password": "test1234"}).json["access_token"]
r = c.get("/api/admin/users", headers={"Authorization": f"Bearer {tok}"})
check("Nutzer mit JWT -> 403", r.status_code == 403)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
