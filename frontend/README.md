# Astra – Frontend

React-basiertes Frontend für das Astra-Projekt (Vite + TypeScript).

## Voraussetzungen

- Node.js 20+
- npm

## Installation

```bash
cd frontend
npm install
```

## Starten

```bash
npm run dev
```

Das Frontend läuft dann auf `http://localhost:3000`.

API-Requests an `/api/*` werden automatisch an das Backend (`http://localhost:5000`) proxied.

## Routen

| Route               | Seite               |
|----------------------|---------------------|
| `/login`             | Login               |
| `/`                  | Dashboard           |
| `/admin/agents`      | Agent-Verwaltung    |
| `/admin/blueprints`  | Blueprint-Verwaltung|
| `/admin/instances`   | Instanz-Verwaltung  |
| `/instances/:uuid`   | Instanz-Detail      |

## Projektstruktur

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── app/
│   │   ├── router.tsx
│   │   └── providers.tsx
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── AdminAgentsPage.tsx
│   │   ├── AdminBlueprintsPage.tsx
│   │   ├── AdminInstancesPage.tsx
│   │   └── InstanceDetailPage.tsx
│   └── services/
│       └── api.ts
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```
