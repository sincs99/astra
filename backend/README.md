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

## Health-Checks

| Route                | Beschreibung       |
|----------------------|--------------------|
| `/health`            | Globaler Check     |
| `/api/admin/health`  | Admin-Bereich      |
| `/api/client/health` | Client-Bereich     |
| `/api/agent/health`  | Agent-Bereich      |
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
│   │   ├── agent/routes.py
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
