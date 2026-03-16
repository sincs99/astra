# SSH-Key-basierte SFTP-Authentifizierung

> Eingeführt in M30 – aufbauend auf dem SSH-Key-Management aus M28 und dem Suspension-System aus M29.

## Überblick

Astra dient als zentrale Kontrollinstanz für SFTP-/SSH-Key-Authentifizierungsentscheidungen. Wenn sich ein Benutzer mit einem SSH-Key über SFTP verbinden möchte, fragt der Agent (Wings-Daemon) das Panel, ob der Zugriff erlaubt ist. Das Panel prüft User, Key, Berechtigungen und den Instance-Status.

Es wird kein vollständiger SSH-Server in Astra betrieben. Astra entscheidet nur, ob ein Zugriff erlaubt ist.

---

## Unterstützte Key-Typen

| Typ | Format |
|---|---|
| `ssh-ed25519` | Empfohlen |
| `ssh-rsa` | Unterstützt |
| `ecdsa-sha2-nistp256` | Unterstützt |
| `ecdsa-sha2-nistp384` | Unterstützt |
| `ecdsa-sha2-nistp521` | Unterstützt |

Fingerprints werden ausschliesslich serverseitig im OpenSSH-Format berechnet (`SHA256:<base64>`). Private Keys werden **nie** gespeichert oder verarbeitet.

---

## Verwaltung von SSH Keys

Benutzer verwalten ihre SSH Public Keys unter `/account/ssh-keys` im Frontend oder über die API:

```
GET    /api/client/account/ssh-keys
POST   /api/client/account/ssh-keys        { "name": "...", "public_key": "ssh-ed25519 AAAA..." }
PATCH  /api/client/account/ssh-keys/<id>   { "name": "..." }
DELETE /api/client/account/ssh-keys/<id>
```

Jeder Key wird einmalig pro Benutzer gespeichert (Fingerprint-Unique-Constraint). Beim Löschen eines Keys wird der SFTP-Zugriff für diesen Key sofort widerrufen.

---

## Zuordnung: Benutzer ↔ Instance

Der SFTP-Zugriff wird für eine konkrete Instance geprüft. Der Agent sendet bei jeder Verbindung folgendes an das Panel:

| Feld | Beschreibung |
|---|---|
| `username` | Astra-Benutzername |
| `instance_uuid` | UUID der Ziel-Instance |
| `public_key` | SSH Public Key (bevorzugt) |
| `fingerprint` | Alternativ: SHA256-Fingerprint |

Mindestens `public_key` oder `fingerprint` muss angegeben werden. Der `public_key` wird bevorzugt, da der Fingerprint dann serverseitig berechnet wird.

---

## Berechtigungen

### Owner

Ein Benutzer, der **Owner** einer Instance ist, erhält automatisch SFTP-Zugriff, sofern die Instance nicht suspendiert ist. Keine zusätzliche Berechtigung erforderlich.

### Collaborator

Ein Collaborator benötigt die Berechtigung **`file.sftp`**, um sich via SFTP einzuloggen. Diese Permission wird vom Instance-Owner unter `/api/client/instances/<uuid>/collaborators` vergeben.

```
POST /api/client/instances/<uuid>/collaborators
{
  "user_id": 42,
  "permissions": ["file.sftp", "file.read"]
}
```

Ohne `file.sftp` wird der SFTP-Zugriff mit `permission_denied` abgelehnt, auch wenn der Collaborator andere Berechtigungen hat.

---

## Suspension

Suspendierte Instances blockieren **jeden** SFTP-/SSH-Key-Zugriff, unabhängig von Benutzerrolle oder Schlüssel. Die Antwort lautet:

```json
{ "allowed": false, "reason": "instance_suspended" }
```

Nur ein Administrator kann die Suspension aufheben (`POST /api/admin/instances/<uuid>/unsuspend`).

---

## Agent-API-Endpunkt

```
POST /agent/sftp-auth
```

**Request-Body:**

```json
{
  "username":      "johndoe",
  "instance_uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "public_key":    "ssh-ed25519 AAAA..."
}
```

**Erfolgreiche Antwort:**

```json
{
  "allowed":       true,
  "username":      "johndoe",
  "instance_uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "permissions":   ["file.read", "file.update", "file.sftp", ...]
}
```

**Abgelehnte Antwort:**

```json
{
  "allowed": false,
  "reason":  "instance_suspended"
}
```

### Mögliche `reason`-Werte

| Wert | Bedeutung |
|---|---|
| `ok` | Zugriff erlaubt (nur bei `allowed: true`) |
| `user_unknown` | Benutzername nicht gefunden |
| `instance_not_found` | Instance-UUID nicht vorhanden |
| `key_unknown` | Key/Fingerprint dem Benutzer nicht bekannt |
| `permission_denied` | Collaborator hat keine `file.sftp`-Berechtigung |
| `instance_suspended` | Instance ist administrativ gesperrt |
| `malformed_request` | Request-Body unvollständig |

---

## Passwort- vs. Key-Authentifizierung

M30 implementiert ausschliesslich **Public-Key-Authentifizierung**. Passwortbasierter SFTP-Login ist nicht Teil dieser Implementierung. Die Auth-Typen sind klar getrennt:

- Key-Auth → `POST /agent/sftp-auth` mit `public_key` oder `fingerprint`
- Passwort-Auth → nicht implementiert

---

## Activity- und Webhook-Events

| Event | Beschreibung |
|---|---|
| `ssh_key:auth_success` | SFTP-Key-Auth erfolgreich |
| `ssh_key:auth_failed` | SFTP-Key-Auth abgelehnt (Grund wird mitgeloggt) |

Bei Auth-Fehlern werden **keine** Public-Key-Daten geloggt – nur der Fingerprint (wenn bekannt), Benutzername und Ablehnungsgrund.

---

## Sicherheitshinweise

- Private Keys werden **nie** verarbeitet, gespeichert oder geloggt
- Fingerprints werden **serverseitig** berechnet – dem Agent wird kein Fingerprint blind vertraut
- Auth-Entscheidungen sind **zentral** im Panel, nicht im Agent
- Suspendierte Instances können **nicht** umgangen werden (kein Bypass über SSH-Key-Login)
- Jeder Auth-Versuch wird in der Activity-Log erfasst (ohne sensible Daten)
