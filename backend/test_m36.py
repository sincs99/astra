"""M36 – Node-Token-Guard fuer /api/agent."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.blueprints.models import Blueprint
from app.domain.instances.models import Instance
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
app.config["AGENT_GUARD_ENABLED"] = True

with app.app_context():
    db.create_all()
    owner = User(username="o", email="o@t.local")
    owner.set_password("test1234")
    a1 = Agent(name="n1", fqdn="n1.test")
    a1.generate_daemon_credentials()
    a2 = Agent(name="n2", fqdn="n2.test")
    a2.generate_daemon_credentials()
    db.session.add_all([owner, a1, a2])
    db.session.flush()
    bp = Blueprint(name="b", docker_image="img", startup_command="run", install_script="echo")
    db.session.add(bp)
    db.session.flush()
    i1 = Instance(name="i1", owner_id=owner.id, agent_id=a1.id, blueprint_id=bp.id)
    i2 = Instance(name="i2", owner_id=owner.id, agent_id=a2.id, blueprint_id=bp.id)
    db.session.add_all([i1, i2])
    db.session.commit()
    u1, u2, i1_id = i1.uuid, i2.uuid, i1.id
    tok1 = f"{a1.daemon_token_id}.{a1.daemon_token}"
    tok2 = f"{a2.daemon_token_id}.{a2.daemon_token}"
    tid1 = a1.daemon_token_id

c = app.test_client()
bearer = lambda t: {"Authorization": f"Bearer {t}"}

print("Ohne / mit falschem Token")
check("/health bleibt offen", c.get("/api/agent/health").status_code == 200)
for path, body in [
    (f"/api/agent/instances/{u1}/install", {"successful": True}),
    (f"/api/agent/instances/{u1}/container/status", {"state": "running"}),
    ("/api/agent/sftp-auth", {"username": "o", "instance_uuid": u1, "fingerprint": "SHA256:x"}),
]:
    check(f"{path} ohne Token -> 401", c.post(path, json=body).status_code == 401)
    r = c.post(path, json=body, headers=bearer(f"{tid1}.falsch"))
    check(f"{path} falscher Token -> 403", r.status_code == 403, str(r.status_code))
    r = c.post(path, json=body, headers={"X-User-Id": "1"})
    check(f"{path} X-User-Id reicht nicht -> 401", r.status_code == 401)

print("Eigener Node")
r = c.post(f"/api/agent/instances/{u1}/container/status", json={"state": "running"}, headers=bearer(tok1))
check("container/status eigene Instanz -> 200", r.status_code == 200, r.get_data(as_text=True))
r = c.post(f"/api/agent/instances/{u1}/install", json={"successful": True}, headers=bearer(tok1))
check("install eigene Instanz -> 200", r.status_code == 200, r.get_data(as_text=True))
r = c.post("/api/agent/sftp-auth", json={"username": "o", "instance_uuid": u1, "fingerprint": "SHA256:x"},
           headers=bearer(tok1))
check("sftp-auth eigene Instanz -> 200", r.status_code == 200 and r.json.get("allowed") is False)

print("Fremder Node")
r = c.post(f"/api/agent/instances/{u1}/container/status", json={"state": "offline"}, headers=bearer(tok2))
check("container/status fremde Instanz -> 403", r.status_code == 403, str(r.status_code))
r = c.post(f"/api/agent/instances/{u1}/install", json={"successful": False}, headers=bearer(tok2))
check("install fremde Instanz -> 403", r.status_code == 403, str(r.status_code))
r = c.post("/api/agent/sftp-auth", json={"username": "o", "instance_uuid": u1, "fingerprint": "SHA256:x"},
           headers=bearer(tok2))
check("sftp-auth fremde Instanz -> allowed=false", r.json.get("reason") == "instance_not_on_node", str(r.json))
with app.app_context():
    check("fremder Node hat Status nicht veraendert",
          db.session.get(Instance, i1_id).container_state != "offline")

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
