# MFA-Recovery-Codes

Wer den Authenticator verliert, meldet sich mit einem einmaligen Recovery-Code an. Gilt ab M60.

## Verhalten

- Beim Aktivieren von MFA (`POST /api/auth/mfa/verify`) erzeugt Astra **10 Codes** im Format `xxxxx-xxxxx`
  (Kleinbuchstaben und Ziffern ohne leicht verwechselbare Zeichen). Der Klartext steht **nur in dieser Antwort**;
  gespeichert werden ausschließlich gesalzene Hashes (`users.mfa_recovery_codes`).
- Jeder Code gilt **einmal**. Groß-/Kleinschreibung, Bindestrich und Leerzeichen spielen keine Rolle.
- Neue Codes erzeugen (alte werden sofort ungültig): `POST /api/auth/mfa/recovery-codes`.
- MFA deaktivieren löscht alle Codes. Fehlversuche verbrauchen keinen Code.
- Wird ein Code verwendet, bekommt der Kontoinhaber eine Mail, es entsteht das Activity-Event
  `auth:mfa_recovery_used`; ab 2 verbleibenden Codes enthält die Mail einen Hinweis auf neue Codes.
- Vor M60 gespeicherte Klartext-Codes werden von der Migration `t0o1p2q3r4s5` gehasht und bleiben gültig.
  Ein Downgrade stellt den Klartext nicht wieder her (betroffene Nutzer erzeugen neue Codes).

## API

| Aufruf | Antwort |
|---|---|
| `POST /api/auth/mfa/verify` `{code}` | `{mfa_enabled: true, recovery_codes: [10 Codes], recovery_codes_remaining: 10, message}` |
| `POST /api/auth/mfa/recovery-codes` `{password}` (angemeldet) | `{recovery_codes: [10 Codes], recovery_codes_remaining: 10, message}`; falsches oder fehlendes Passwort: **403** `{error, code: "invalid_password"}`; MFA nicht aktiv: **409**; ohne Anmeldung: 401 |
| `POST /api/auth/login` `{login, password, mfa_code}` | `mfa_code` ist ein TOTP-Code **oder** ein Recovery-Code (alternativ das Feld `recovery_code`). Erfolg wie bisher; wurde ein Recovery-Code verwendet, zusätzlich `recovery_code_used: true` und `recovery_codes_remaining`. Ungültig: 401 `Ungültiger MFA-Code` |
| `GET /api/auth/me`, Login-Antwort `user` | enthält `mfa_recovery_codes_remaining` (0, wenn MFA aus ist); nie Codes oder Hashes |

Sechsstellige Ziffern sind immer TOTP und werden nie als Recovery-Code geprüft.

## Grenzen

- Kein Zurücksetzen von MFA per E-Mail-Link; wer weder Authenticator noch Codes hat, braucht einen Admin.
- MFA deaktivieren verlangt weiterhin kein Passwort (unverändert seit M19).
