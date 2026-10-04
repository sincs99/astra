# Astra – Design-Richtlinien für die Umsetzung

Diese Datei ist für Claude Code (und Menschen) gedacht. Sie beschreibt, wie das Astra-Panel aussieht und sich verhält. Die Werte stehen in `tokens.css` (CSS-Variablen, dunkel + hell) und `tokens.json`. Die Mockups unter `mockups/` sind die visuelle Referenz – im Browser öffnen, Markup und Inline-Styles als Vorlage nehmen.

## Charakter

Dunkel, ruhig, technisch, freundlich. Vorbilder: Vercel, Linear, Railway. Kein Neon, keine Glow-Effekte, keine Gradienten-Buttons, keine Glassmorphism-Flächen, keine Stock-Illustrationen. Die Landingpage darf werben, das Panel nicht. Texte kurz, deutsch, Du-Form.

## Farben

- Immer die CSS-Variablen aus `tokens.css` verwenden, nie Hex-Werte im Komponenten-Code.
- Dunkel ist Standard. Hell über `<html data-theme="light">`.
- Genau eine Akzentfarbe (`--accent`): Links, Primärbutton, Fokusring, aktiver Nav-Eintrag, Logo. Sparsam.
- Text auf Akzentfläche ist `--on-accent` (dunkel im Dark-Theme, weiß im Light-Theme), nie fest weiß.
- Statusfarben überall gleich: `--ok` = läuft/bezahlt/gesund, `--warn` = wartet/Warnung/bald fällig, `--danger` = gestoppt/Fehler/überfällig/löschen, `--neutral` = inaktiv/unbekannt.
- Primärtext `--text` (helles Grau, kein Weiß), Sekundärtext `--text-2`, Beschriftungen `--text-3`. Alle Kombinationen erfüllen WCAG AA.
- Konsole ist der dunkelste Bereich (`--console`), auch im hellen Theme.

## Typografie

- UI: `--font-ui` (Geist, Fallback Inter), 14 px Grundgröße, Zeilenhöhe 1,5.
- Hierarchie über Gewicht: Seitentitel 24/600, Kartentitel 16/600, Beschriftung 14/500, Fließtext 14/400 in `--text-2`, Hinweis 12/400 in `--text-3`. Keine weiteren Größen erfinden.
- Monospace (`--font-mono`) für Konsole, Logs, IP-Adressen, Ports, Server-IDs, Bestellnummern, Verwendungszwecke, IBAN.
- Zahlen in Tabellen und Kacheln mit `font-variant-numeric: tabular-nums`, rechtsbündig.

## Layout

- App-Shell: Seitenleiste links 240 px (`--surface`, rechte Kante `--border`), einklappbar auf 56 px (nur Icons, `aria-label`). Oben Logo, dann Navigation (Icon + Text), unten Nutzermenü mit Avatar-Initialen, Sprache, Theme, Abmelden.
- Inhalt: `max-width: 1200px`, 24 px Außenabstand, 16 px zwischen Karten. Karten `--surface`, 1 px `--border`, Radius 8 px.
- Kopfzeile pro Seite: Titel + einzeiliger Untertitel links, primäre Aktionen rechts, umbrechend.
- Hinweis-/Warnbanner oben im Inhalt: Punkt in Statusfarbe, ein Satz, rechts eine Aktion. Hintergrund `--warn-soft`/`--danger-soft`, Rahmen `--warn-border`/`--danger-border`.
- Mobil ab 390 px: Seitenleiste wird Kopfzeile mit Hamburger und Vollbild-Overlay; Tabellen werden Karten; Aktionen in Drei-Punkte-Menü; Touch-Ziele 44 px; kein horizontales Scrollen auf Kundenseiten. Admin-Tabellen dürfen in einer Box mit `overflow-x: auto` scrollen.

## Komponenten (siehe `mockups/Components.html`)

- **Button**: Höhe 36 px (klein 32, Touch 44), Radius 6 px, Gewicht 500. Primär = `--accent`/`--on-accent`. Sekundär = `--surface-2` mit `--border`. Gefährlich = `--danger` mit weißem Text. Geist = transparent, `--text-2`. Icon-only immer mit `aria-label`. Fokus: 2 px Ring in `--accent` mit 2 px Abstand.
- **Input/Select**: 36 px, `--surface-2`, `--border`, Radius 6 px; Fokus `--accent` + weicher Ring; Fehler `--danger` + Meldung darunter. Label immer sichtbar und per `for` verbunden.
- **Status-Badge**: 7 px Punkt + Text, 12/500, `--surface-2`, 1 px `--border`, Radius 4 px. Immer dieselbe Form, nur Punktfarbe und Text wechseln. Wartungsmodus nutzt `--accent-soft`.
- **Statistik-Kachel**: Zahl 28/600 tabular, Beschriftung 13 in `--text-2`, optional Trend/Zusatz 12 in Statusfarbe.
- **Kapazitätsbalken**: 6 px, Radius 3 px, Spur `--surface-2`; Füllung `--accent`, ab ~80 % `--warn`, über 100 % `--danger` plus schraffierter Überbuchungsanteil (`repeating-linear-gradient 135deg`).
- **Tabelle**: Kopf `--surface-2` 12/500 `--text-2`, Zeilen 1 px `--border-soft`, Hover `#1a2029`, IDs mono, Beträge rechts tabular, letzte Spalte Drei-Punkte-Menü.
- **Tabs**: Textlinks mit 2 px Unterstrich in `--accent` für aktiv, sonst `--text-2`. Keine Pill-Tabs.
- **Toast**: unten rechts, `--surface`, `--border`, Radius 8 px, Punkt in Statusfarbe, ein Satz, Schließen-X. Kein Icon-Feuerwerk.
- **Leerzustand**: gestrichelter Rahmen, ein Satz, eine Aktion („Noch kein Server. Zum Shop.“).
- **Lade-Skelett** statt Spinner, Balken in `--surface-2`, 4 px Radius.
- **Bestätigungs-Dialog** (destruktiv): Titel mit Objektname, ein Absatz Folgen, Eingabe des Namens als Sicherung, Primärbutton `--danger` bis zur Eingabe deaktiviert.
- **Konsole**: `--console`, mono 12,5 px, Zeilenhöhe 1,65, Zeitstempel `--text-3`, INFO `--ok`, WARN `--warn`, ERROR `--danger`; Eingabezeile unten mit `›`-Prompt; Start/Stop/Neustart/Kill als sekundäre Buttons, Stop und Kill in `--danger`.

## Bewegung

Nur Übergänge von 150–200 ms (Hover, Fokus, Tabs, Dialog ein/aus) und der Live-Stream der Konsole. Keine Einflug-Animationen, keine Parallaxe.

## Barrierefreiheit

Echte `<button>`, `<a href>`, `<input>` mit `<label>`; nie `onClick` auf `div`. Icon-only-Buttons mit `aria-label`. Status nie nur über Farbe: immer Punkt + Text. Kontrast mindestens 4,5:1 für Text, 3:1 ab 24 px. Live-Regionen (`role="status"`, `role="alert"`) für Banner und Toasts.

## Logo

Wortmarke „Astra“ in Geist 600, Laufweite −3 %, davor ein Vier-Strahl-Stern (32er-Raster, Spitzen bei 3 und 29) mit Satellitenpunkt bei (26, 6). Stern in `--accent`, Punkt in `--text`. Unter 24 px nur der Stern ohne Punkt. Die SVG-Pfade stehen in `mockups/Logo.html`.
