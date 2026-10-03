# Astra – Backend

Flask-basiertes Backend für das Astra-Projekt.

## Voraussetzungen

- Python 3.11+
- pip

## Installation

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

pip install -r requirements.txt

cp .env.example .env
```

## Starten

```bash
python run.py
```

Das Backend läuft dann auf `http://localhost:5000`.

## Meldungen mit Umlauten

API-Meldungen für Kunden (Auth, Client, Billing, Mails) werden mit echten Umlauten geschrieben („Ungültige Anmeldedaten“,
nicht „Ungueltige Anmeldedaten“). `python tools/umlauts.py` prüft die Kundendateien auf ASCII-Schreibweisen,
`python tools/umlauts.py --write` korrigiert sie; neue Wörter kommen in das Wörterbuch `WORDS`. `test_m50.py`
schlägt bei einem Treffer fehl. Fehlercodes, Statuswerte und Ereignisnamen bleiben immer englisch/ASCII.

## Health-Checks

| Route                | Beschreibung       |
|----------------------|--------------------|
| `/health`            | Globaler Check     |
| `/api/admin/health`  | Admin-Bereich      |
| `/api/client/health` | Client-Bereich     |
| `/api/auth/health`   | Auth-Bereich       |

## Projektstruktur

```
backend/
├── app/
│   ├── __init__.py          # App Factory
│   ├── config.py            # Konfiguration
│   ├── extensions.py        # Flask-Erweiterungen
│   ├── api/
│   │   ├── admin/routes.py
│   │   ├── client/routes.py
│   │   ├── remote/routes.py   # Wings Remote-API (Node-Token)
│   │   └── auth/routes.py
│   └── domain/
│       ├── users/models.py
│       ├── agents/models.py
│       ├── blueprints/models.py
│       ├── instances/models.py
│       └── endpoints/models.py
├── run.py
├── requirements.txt
└── .env.example
```
