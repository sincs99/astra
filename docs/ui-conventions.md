# UI-Konventionen

Kurzfassung und Checkliste für neue Seiten. Das visuelle Regelwerk steht in `design/DESIGN.md`, die Referenz-Mockups in
`design/mockups/*.html`. Hier steht, wie das im Frontend (`frontend/src`) umgesetzt ist.

## Checkliste für eine neue Seite

1. Passendes Mockup in `design/mockups/` lesen und Markup/Stil übernehmen; was dort fehlt, nicht erfinden.
2. Seitenrahmen mit `PageLayout` (`title`, `subtitle`, `actions`, `back`, `maxWidth`).
3. Farben, Schrift, Abstände nur über Tokens/Klassen (siehe unten), **keine Hex-Werte** im Komponenten-Code.
4. Jeder sichtbare Text über `t()` (DE und EN), neue Schlüssel im passenden Namespace.
5. Tabellen mit `tbl tbl-cards`, `th scope="col"` und `data-label` an jeder Zelle.
6. Lade-/Fehler-/Leerzustand vorhanden (`LoadingState`, `ErrorState`, `EmptyState`).
7. Destruktive Aktionen mit `ConfirmButton` (oder eigenem Dialog mit Namenseingabe).
8. Formularfelder mit Label, Fehler als `role="alert"`, Erfolg als `role="status"`, Icon-Buttons mit `aria-label`.
9. Test (`// @vitest-environment jsdom`) mit Liste, Hauptaktion, Fehlerzustand und EN-Anzeige.
10. `npx tsc --noEmit -p .`, `npx vitest run`, `npm run build`; bei Kundenfluss zusätzlich `./e2e/run-local.sh`
    (enthält die automatische Barrierefreiheitsprüfung `e2e/a11y.mjs`).

## Design-Tokens

- Quelle ist `design/tokens.css` (und `tokens.json`). Das Frontend nutzt die Kopie `frontend/src/styles/tokens.css`
  (der Docker-Build-Kontext ist `frontend/`). Nach jeder Änderung an der Quelle: `npm run sync:tokens`, die Kopie nie von Hand bearbeiten.
- `src/theme.css` importiert Tokens und die Stylesheets (`shell.css`, `ui.css`, `landing.css`) und ergänzt nur `color-scheme` und
  abgeleitete Werte (`--console-dim`). Es gibt keine Kompatibilitäts-Aliase mehr; alte Namen wie `--bg-card`, `--fg-muted`, `--c-red`,
  `--tint-*` dürfen nicht neu auftauchen.
- Wichtige Tokens: Flächen `--bg`, `--surface`, `--surface-2`; Text `--text`, `--text-2`, `--text-3`; Akzent `--accent`/`--accent-soft`/`--on-accent`;
  Status `--ok`, `--warn`, `--danger` (jeweils `-soft`, `-border`; `--on-danger` für Text auf Danger-Flächen); Konsole `--console`, `--text-console`;
  Maße `--radius-card`, `--radius-btn`, `--control-h`, `--control-h-touch`, Schriftgrößen `--fs-*`.
- Kontrast: Text erfüllt WCAG AA. `--text-3` ist der hellste erlaubte Textton; Akzent-Text auf `--accent-soft` und `--ok` sind in den Tokens korrigiert.

## Bausteine aus `ui.css`

| Klasse | Zweck |
|---|---|
| `.btn`, `.btn-sm`, `.btn-lg`, `.btn-primary`, `.btn-danger`, `.btn-danger-text`, `.btn-ghost`, `.btn-icon` | Buttons (Primär nur einmal pro Bereich) |
| `.card`, `.card-title`, `.card-sub`, `.card-empty`, `.cards-grid` | Karten und Leerzustand |
| `.panel`, `.panel-head`, `.panel-body`, `.panel-foot`, `.panel-title` | Abschnitte mit Kopf (Formulare, Tabellen) |
| `.banner`, `.banner-info/-warn/-danger`, `.banner-text` | Hinweise; Gefahr mit `role="alert"`, sonst `role="status"` |
| `.kv-list`, `.kv` | Schlüssel/Wert-Zeilen; `.mono` für IDs, Adressen, Zahlen |
| `.addr` | Adresszeile in Konsolenfarbe mit Kopieren-Button (`AddressRow`) |
| `.bar`, `.bar-warn/-danger/-hatch/-nodata/-stack` | Auslastungsbalken; Warnfarbe ab 80 %, „überbucht“ schraffiert |
| `.tbl`, `.tbl-cards`, `.num` | Tabellen; mobil werden Zeilen zu Karten (`data-label` an jeder `td`) |
| `.tabs`, `.tab` | Tabs mit `role="tablist"`, Tastatursteuerung, `?tab=` in der URL |
| `.field`, `.fieldset`, `.inp`, `.hint` | Formulare |
| `.tiles`, `.tile` | Kennzahlenkacheln |
| `.pcard`, `.pkgs`, `.summary` | Shop (Paketwahl, Zusammenfassung) |
| `.lp-*` | Nur die öffentliche Landingpage (`landing.css`) |

Icons kommen aus `components/ui/Icon.tsx` (24er-Raster, 2 px Strich, `currentColor`, immer dekorativ). Fehlt ein Icon, wird es dort ergänzt;
keine Emojis als Icons.

## Status-Anzeige

`StatusBadge` zeigt Punkt + Text, nie Farbe allein: grün (`ok`) für bereit/läuft/bezahlt/aktiv, gelb (`warn`) für ausstehend/wartet/bald fällig,
rot (`danger`) für Fehler/überfällig/gesperrt/**nicht erreichbar**, grau (`neutral`) für gestoppt/unbekannt/inaktiv, Akzent für laufende Vorgänge
(Einrichtung, Neuinstallation). Der Text kommt aus den `status.*`-Schlüsseln; unbekannte API-Werte werden roh angezeigt.

## Texte und Sprachen (i18n)

- `src/i18n/index.ts`: `t(key, params)`, `useLang`, `setLang`, `dateLocale()`, `moneyLocale()`, `hasKey`. Deutsch ist Standard, Englisch umschaltbar
  (Konto, Login, Landing); `LangRoot` baut den Baum beim Wechsel neu auf.
- Wörterbücher je Namespace in `src/i18n/de/*.ts` und `src/i18n/en/*.ts` (`common`, `nav`, `auth`, `account`, `dash`, `shop`, `orders`, `landing`,
  `srv` + `sconsole/sfiles/sbackups/sroutines/susers/sform` für Server-Detail, `aorders/aagents/ainst/asys/aover` für den Admin-Bereich). Schlüssel haben das
  Präfix des Namespaces (`dash.rowTerm`). `de.ts` bestimmt die Schlüssel, `en.ts` ist typgeprüft (fehlt einer, bricht `tsc`); ein Test prüft gleiche Platzhalter.
- Platzhalter `{name}`; **keine „(en)“-Plurale**, sondern getrennte Schlüssel (`…One`/`…Other`) mit `Intl.PluralRules(dateLocale())` (siehe `plural()` in `lib/adminOverview.ts`).
- Datum, Zahl, Währung, Relativzeit nur über `formatDateTime`/`formatMoney`/`formatTimeAgo`/`Intl`, nie feste `de-DE`-Strings.
- Texte vom Server (Fehlermeldungen, Backup-/Restore-Antworten, Aktivitätsbeschreibungen) bleiben deutsch und werden unverändert angezeigt.
- **Fehlertexte der API (M72):** jede Fehlerantwort von `/api/auth` und `/api/client` ist `{error, code}`. Der API-Client sendet bei jedem Request `Accept-Language` mit der
  UI-Sprache (`de`/`en`); angemeldete Nutzer bekommen die Sprache aus `users.locale`. Im Code **auf `code` verzweigen**, `error` nur anzeigen (siehe `docs/orders-api.md` → Fehlerformat).
- **Servertexte folgen `users.locale` (M67):** Mails (Bestätigung, Passwort-Reset, Zahlung, Server bereit, Erinnerung, Sperre, Löschhinweis, Beendet, Erstattung,
  Recovery-Code) und Zahlungsbelege (HTML/Text) rendert das Backend in der Sprache des Kunden (`de` Standard, `en`). Das Frontend setzt sie mit
  `PATCH /api/client/account {locale}` (beim Sprachwechsel im Konto mitsenden; `/api/auth/me` liefert `locale`) und bei der Registrierung optional mit `locale` im Body.
  Admin-Alerts, Fehlermeldungen der API und Activity-Beschreibungen bleiben deutsch. Neue Servertexte gehören in `backend/app/i18n/messages.py` (gleiche Schlüssel und
  Platzhalter in `de` und `en`, ein Test prüft das).
- Wortstellung mit eingebettetem Element (z. B. `<code>`) über einen Platzhalter und Split (siehe `ui/TypeName.tsx`).

## Theme

- Dunkel ist der Standard. `lib/theme.ts` kennt `system | light | dark` (localStorage `astra_theme`, Auswahl unter Konto → Darstellung), löst „system“ über
  `prefers-color-scheme` auf und setzt `data-theme` am `<html>`. Ein Inline-Skript in `index.html` setzt es vor dem ersten Rendern (kein Aufblitzen).
- Komponenten dürfen `data-theme` nicht selbst prüfen; sie nutzen Tokens, die sich mit dem Theme ändern. Die Server-Konsole bleibt in beiden Themes dunkel.
- Schrift: Geist/Geist Mono self-hosted über `@fontsource` (kein Google-Fonts-Link).

## Mobil

- Breakpoint 760 px: Seitenleiste wird zur Kopfzeile mit Menü-Overlay, Tabellen mit `tbl-cards` zu Karten, Buttons/Eingaben mit Touch-Höhe
  (`--control-h-touch`, 44 px). Kein horizontales Seiten-Scrollen; breite Tabellen/Konsolen nur in fokussierbaren Bereichen
  (`role="region" tabIndex={0} aria-label=…` oder `ScrollRegion`).
- Die Sprungmarke „Zum Inhalt“ (`SkipLink`) und der Seitentitel im Tab (`document.title`) gehören zu jeder Seite über `PageLayout`.

## Gefährliche Aktionen

`ConfirmButton` (Text, `danger` für rot) für Löschen, Rotieren, Neuinstallieren, Kill. Wo ein Fehlgriff Daten kostet, zusätzlich Namenseingabe
(`DeleteInstanceForm`, `TransferInstanceForm`). Toasts (`useToast`) nur für kurze Rückmeldungen; Fehler in Formularen stehen im Formular.

## Bewusst nicht aus den Mockups übernommen

Alles, was die API nicht belegt, bleibt weg („nichts erfunden“). Der Umsatztrend erscheint nur, wenn `/admin/stats/revenue` einen Vorzeitraum > 0 liefert (sonst „kein Vergleich“, bei älterem Backend keine Zeile):
Spielerzahlen, RAM-Auslastung im Dashboard, Betrag je Zahlungsereignis, „Erinnerung senden“, nächster Tick-Lauf;
auf der Landingpage „Server in Deutschland“, „Tägliche Backups“, „Beliebt“-Marke, MwSt-Hinweis, feste Spieleliste (nur aus Blueprint-Namen), „monatlich kündbar“;
IBAN/Verwendungszweck stehen nur, wo das Backend sie liefert (`payment_purpose`) bzw. der Betreiber sie in `legal/payment.ts` pflegt.
Die Überschrift „In drei Minuten online, ohne Linux“ ist Mockup-Text und vom Betreiber zu bestätigen.
Farbige Ereignis-Badges im Aktivitätslog entfallen (keine Tokens dafür), ebenso Marken-Logos bei Spielen.

## Tests

- Tests dürfen nie vom Inhalt von `legal/operator.ts` abhängen (der Betreiber trägt dort echte Daten ein): `src/test/setup.ts` ersetzt das Modul in allen Tests durch eine Fixture (brand „Astra“, jurisdiction „DE“, Platzhalter). Wer einen anderen Wert braucht, setzt ihn im Test gezielt (`OPERATOR.jurisdiction = "CH"`) und danach zurück; `legal/operator.test.ts` prüft nur die Form der echten Datei.

- Vitest + Testing Library + jsdom (`vitest run`); API per `vi.spyOn(api, …)`, Sprache per `setLang` und in `afterEach` zurück auf `de`.
- `e2e/flow.mjs` (Kundenfluss gegen das echte Backend) und `e2e/a11y.mjs` (axe A/AA) über `./e2e/run-local.sh`, siehe `frontend/e2e/README.md`.
