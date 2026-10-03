"""M40 – Rueckbau der Legacy-Routen unter /api/agent."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db

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
c = app.test_client()

print("Legacy-Routen sind weg")
for method, path in [
    ("get", "/api/agent/health"),
    ("post", "/api/agent/instances/abc/install"),
    ("post", "/api/agent/instances/abc/container/status"),
    ("post", "/api/agent/sftp-auth"),
]:
    check(f"{method.upper()} {path} -> 404", getattr(c, method)(path, json={}).status_code == 404)
check("keine Route mit Praefix /api/agent registriert",
      not [r.rule for r in app.url_map.iter_rules() if r.rule.startswith("/api/agent")])
check("kein Blueprint 'agent' registriert", "agent" not in app.blueprints)
check("Config kennt AGENT_GUARD_ENABLED nicht mehr", "AGENT_GUARD_ENABLED" not in app.config)

print("Ersatz /api/remote bleibt geschuetzt")
check("GET /api/remote/servers ohne Token -> 401", c.get("/api/remote/servers").status_code == 401)
check("POST /api/remote/sftp/auth ohne Token -> 401", c.post("/api/remote/sftp/auth", json={}).status_code == 401)
check("POST /api/remote/servers/x/install ohne Token -> 401",
      c.post("/api/remote/servers/x/install", json={"successful": True}).status_code == 401)
check("POST /api/remote/servers/x/container/status ohne Token -> 401",
      c.post("/api/remote/servers/x/container/status", json={}).status_code == 401)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
