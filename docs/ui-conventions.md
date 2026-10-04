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

**Dunkler Modus:** Farben stehen als CSS-Variablen in `frontend/src/theme.css` (`--bg-card`, `--fg-muted`, `--c-green`, `--tint-red`, `--border` usw.) und werden in Komponenten als `var(--...)` verwendet, nicht als Hex. Die Hex-Werte in den Tabellen unten sind die Werte des hellen Designs. Dunkel gilt bei `prefers-color-scheme: dark` oder `data-theme="dark"`; der Nutzer waehlt im Konto "Wie das Gerät", "Hell" oder "Dunkel" (localStorage `astra_theme`). Gesaettigte Flaechen mit weissem Text (Buttons, Power-Buttons) bleiben bewusst feste Hex-Werte, ebenso die Server-Konsole (immer dunkel).

### Status-Farben

| Farbe | Hex | Verwendung |
|-------|-----|-----------|
| Gruen | `#2e7d32` | ready, running, healthy, completed, ok, active, success |
| Blau | `#1565c0` | provisioning, starting, pending, info, reinstalling |
| Orange | `#bf360c` | stale, retrying, warning, maintenance, restoring, stopping |
| Rot | `#c62828` | failed, error, degraded, stopped, provision_failed |
| Lila | `#7b1fa2` | retrying (Jobs) |
| Grau | `#666` | offline, unknown, inactive, unreachable, none |

### Background-Farben (Badges)

Immer heller Hintergrund mit dunkler Schrift:
- Gruen: `bg: #e8f5e9, color: #4caf50`
- Blau: `bg: #e3f2fd, color: #1976d2`
- Orange: `bg: #fff3e0, color: #f57c00`
- Rot: `bg: #ffebee, color: #d32f2f`
- Grau: `bg: #f5f5f5, color: #888`

Hinweis: Textfarben erfuellen WCAG AA (Kontrast >= 4.5:1). Fuer Text keine helleren Grautoene als `#666`
und kein `#4caf50` auf hellem Grund verwenden. Jedes Formularfeld braucht ein Label (`htmlFor`/`id`).

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
