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

## Wings-Endpunkt (M33)

Ein echter Wings-Daemon nutzt nicht den unten beschriebenen Astra-internen Endpunkt,
sondern `POST /api/remote/sftp/auth` mit Node-Token-Auth und dem Wings-Format
`{"type": "password"|"public_key", "username": "user.serverid", "password": "..."}`.
Der Public-Key-Pfad ruft intern `authorize_ssh_key_access()` auf, die Regeln dieses
Dokuments gelten also unveraendert. Siehe `docs/wings-remote-api.md`.

## Legacy-Endpunkt entfernt

Der frueher Astra-interne Endpunkt `POST /api/agent/sftp-auth` (mit `username`, `instance_uuid`,
`public_key`/`fingerprint`) wurde mit M40 entfernt. Wings nutzt ausschliesslich `POST /api/remote/sftp/auth`
(siehe oben und `docs/wings-remote-api.md`). Die Pruefregeln dieses Dokuments gelten dort unveraendert,
`authorize_ssh_key_access()` akzeptiert weiterhin `public_key` oder `fingerprint`.


## Passwort- vs. Key-Authentifizierung

M30 implementiert ausschliesslich **Public-Key-Authentifizierung**. Passwortbasierter SFTP-Login ist nicht Teil dieser Implementierung. Die Auth-Typen sind klar getrennt:

- Key-Auth → `POST /api/remote/sftp/auth` mit `type: public_key`
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
