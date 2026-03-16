# UI-Konventionen (M26)

## Zentrale Komponentenbibliothek

Alle gemeinsamen UI-Komponenten befinden sich unter:
`frontend/src/components/ui/`

### Verfuegbare Komponenten

| Komponente | Zweck | Import |
|-----------|-------|--------|
| `StatusBadge` | Einheitliche Status-Anzeige | `import { StatusBadge } from "../components/ui"` |
| `LoadingState` | Ladezustand | `import { LoadingState } from "../components/ui"` |
| `ErrorState` | Fehleranzeige mit Retry | `import { ErrorState } from "../components/ui"` |
| `EmptyState` | Leerzustand | `import { EmptyState } from "../components/ui"` |
| `ConfirmButton` | Button mit Bestaetigungsdialog | `import { ConfirmButton } from "../components/ui"` |
| `Toast/useToast` | Benachrichtigungen | `import { Toast, useToast } from "../components/ui"` |
| `PageLayout` | Seitenlayout mit Navigation | `import { PageLayout } from "../components/ui"` |

### Gemeinsame Styles

```ts
import { cardStyle, inputStyle, labelStyle, btnPrimary, btnDanger, btnDefault, thStyle, tdStyle, linkStyle } from "../components/ui";
```

## Farbkonventionen

### Status-Farben

| Farbe | Hex | Verwendung |
|-------|-----|-----------|
| Gruen | `#4caf50` | ready, running, healthy, completed, ok, active, success |
| Blau | `#1976d2` | provisioning, starting, pending, info, reinstalling |
| Orange | `#f57c00` | stale, retrying, warning, maintenance, restoring, stopping |
| Rot | `#d32f2f` | failed, error, degraded, stopped, provision_failed |
| Lila | `#9c27b0` | retrying (Jobs) |
| Grau | `#888` | offline, unknown, inactive, unreachable, none |

### Background-Farben (Badges)

Immer heller Hintergrund mit dunkler Schrift:
- Gruen: `bg: #e8f5e9, color: #4caf50`
- Blau: `bg: #e3f2fd, color: #1976d2`
- Orange: `bg: #fff3e0, color: #f57c00`
- Rot: `bg: #ffebee, color: #d32f2f`
- Grau: `bg: #f5f5f5, color: #888`

## Loading / Error / Empty States

### Loading
```tsx
<LoadingState message="Daten werden geladen..." />
```

### Error
```tsx
<ErrorState message={error} onRetry={loadData} />
```

### Empty
```tsx
<EmptyState message="Keine Eintraege vorhanden." icon="📭" />
```

## Gefaehrliche Aktionen

Fuer destruktive Aktionen (Delete, Reinstall, etc.):
```tsx
<ConfirmButton
  label="Loeschen"
  confirmMessage="Wirklich loeschen?"
  onConfirm={handleDelete}
  danger
/>
```

## Toast-Benachrichtigungen

```tsx
const toast = useToast();

// Verwenden
toast.success("Erfolgreich gespeichert!");
toast.error("Aktion fehlgeschlagen!");
toast.info("Hinweis: ...");
toast.warning("Achtung: ...");

// Rendern (einmal pro Seite)
<Toast messages={toast.messages} />
```

## Seitenlayout

Alle Admin-Seiten sollten `PageLayout` verwenden:

```tsx
<PageLayout title="Seitentitel" maxWidth={1100}>
  {/* Seiteninhalt */}
</PageLayout>
```

Die Navigation wird automatisch angezeigt mit den Gruppen:
- **Core**: Dashboard, Agents, Blueprints, Instances
- **Operations**: Fleet Monitoring, Jobs, System
- **Integrations**: Webhooks

## Formulare

- Labels: `<label style={labelStyle}>Feldname *</label>`
- Inputs: `<input style={inputStyle} />`
- Pflichtfelder: mit `*` im Label und `required` Attribut
- Submit-Button: waehrend Submit `disabled` setzen
- Fehler: ueber `ErrorState` oder Inline-Meldung

## Tabellen

- Header: `<th style={thStyle}>Spalte</th>`
- Zellen: `<td style={tdStyle}>Wert</td>`
- Leere Tabellen: `<EmptyState>` anstelle leerer `<tbody>`
- Sortierung: wo vorhanden, Sortierrichtung im Header anzeigen

## Responsive

- `maxWidth` auf Seiten verwenden (900-1100px)
- `overflowX: "auto"` fuer breite Tabellen
- `flexWrap: "wrap"` fuer Button-/Filter-Gruppen
- Keine fixen Pixelbreiten fuer Inputs
