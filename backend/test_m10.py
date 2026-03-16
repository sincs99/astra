"""Schnelltests für Meilenstein 10 – Webhooks."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db

app = create_app("testing")
passed = 0
failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  ✅ {label}")


def fail(label, detail=""):
    global failed
    failed += 1
    print(f"  ❌ {label} – {detail}")


def check(label, condition, detail=""):
    if condition:
        ok(label)
    else:
        fail(label, detail)


with app.app_context():
    db.create_all()
    client = app.test_client()

    print("\n── Webhook Event-Katalog ──────────────────────")
    r = client.get("/api/admin/webhooks/events")
    check("GET /webhooks/events → 200", r.status_code == 200)
    events = r.get_json()
    check("Event-Katalog ist Liste", isinstance(events, list))
    check("Event-Katalog hat Einträge", len(events) > 0)
    event_names = [e["event"] for e in events]
    check("instance:created im Katalog", "instance:created" in event_names)
    check("backup:created im Katalog", "backup:created" in event_names)

    print("\n── Webhook CRUD ───────────────────────────────")

    # Erstellen ohne Body
    r = client.post("/api/admin/webhooks", json={})
    check("POST ohne endpoint_url → 400", r.status_code == 400)

    # Erstellen mit ungültiger URL
    r = client.post("/api/admin/webhooks", json={
        "endpoint_url": "not-a-url",
        "events": ["instance:created"],
    })
    check("POST mit ungültiger URL → 400", r.status_code == 400)

    # Erstellen mit ungültigem Event
    r = client.post("/api/admin/webhooks", json={
        "endpoint_url": "https://example.com/hook",
        "events": ["nonexistent:event"],
    })
    check("POST mit ungültigem Event → 400", r.status_code == 400)

    # Erfolgreiches Erstellen
    r = client.post("/api/admin/webhooks", json={
        "endpoint_url": "https://example.com/hook",
        "events": ["instance:created", "backup:created"],
        "description": "Test-Webhook",
    })
    check("POST gültiger Webhook → 201", r.status_code == 201, f"got {r.status_code}: {r.get_json()}")
    wh = r.get_json()
    check("Webhook hat id", "id" in wh)
    check("Webhook hat uuid", "uuid" in wh)
    check("Webhook hat secret_token", bool(wh.get("secret_token")))
    check("Webhook ist aktiv", wh.get("is_active") is True)
    check("Webhook hat 2 Events", len(wh.get("events", [])) == 2)
    wh_id = wh["id"]

    # Auflisten
    r = client.get("/api/admin/webhooks")
    check("GET /webhooks → 200", r.status_code == 200)
    webhooks = r.get_json()
    check("Liste enthält min. 1 Webhook", len(webhooks) >= 1)

    # Aktualisieren
    r = client.patch(f"/api/admin/webhooks/{wh_id}", json={
        "description": "Aktualisierter Test-Webhook",
        "is_active": False,
    })
    check("PATCH Webhook → 200", r.status_code == 200, f"got {r.status_code}: {r.get_json()}")
    updated = r.get_json()
    check("Description aktualisiert", updated.get("description") == "Aktualisierter Test-Webhook")
    check("is_active = False", updated.get("is_active") is False)

    # Aktualisieren mit ungültiger URL
    r = client.patch(f"/api/admin/webhooks/{wh_id}", json={
        "endpoint_url": "ftp://invalid",
    })
    check("PATCH mit ungültiger URL → 400", r.status_code == 400)

    # Nicht gefunden
    r = client.patch("/api/admin/webhooks/99999", json={"description": "x"})
    check("PATCH nicht existierend → 404", r.status_code == 404)

    # Test senden (wird fehlschlagen, da Ziel nicht existiert)
    r = client.post(f"/api/admin/webhooks/{wh_id}/test")
    check("POST /test → 200", r.status_code == 200)
    test_result = r.get_json()
    check("Test-Ergebnis hat success-Feld", "success" in test_result)

    # Löschen
    r = client.delete(f"/api/admin/webhooks/{wh_id}")
    check("DELETE Webhook → 200", r.status_code == 200)

    # Nochmal löschen → 404
    r = client.delete(f"/api/admin/webhooks/{wh_id}")
    check("DELETE nochmal → 404", r.status_code == 404)

    # Leere Liste
    r = client.get("/api/admin/webhooks")
    check("Liste leer nach Löschen", len(r.get_json()) == 0)

    print("\n── Webhook Event-Validierung ──────────────────")
    from app.domain.webhooks.event_catalog import (
        is_valid_webhook_event,
        validate_webhook_events,
        VALID_WEBHOOK_EVENTS,
    )
    check("instance:created ist gültig", is_valid_webhook_event("instance:created"))
    check("nonexistent:event ist ungültig", not is_valid_webhook_event("nonexistent:event"))
    ok_val, invalid = validate_webhook_events(["instance:created", "backup:created"])
    check("validate_webhook_events korrekt", ok_val and len(invalid) == 0)
    ok_val, invalid = validate_webhook_events(["instance:created", "fake:event"])
    check("validate_webhook_events ungültig", not ok_val and "fake:event" in invalid)
    check("Mindestens 12 Events im Katalog", len(VALID_WEBHOOK_EVENTS) >= 12)

    print(f"\n{'='*50}")
    print(f"  Ergebnis: {passed} bestanden, {failed} fehlgeschlagen")
    print(f"{'='*50}\n")

    sys.exit(1 if failed else 0)
