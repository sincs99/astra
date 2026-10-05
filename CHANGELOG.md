# Changelog

Alle relevanten Aenderungen an Astra werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed (Frontend – M76b optionale Betreiberangaben)
- Pflichtfelder in `legal/operator.ts`: brand, jurisdiction, name, street, zipCity, country, email, lastUpdated; alle anderen duerfen leer ("") bleiben (z. B. Telefon, Handelsregister, MWST-Nr., Aufsichtsbehoerde einer Schweizer Einzelfirma). Leere Angaben werden samt Beschriftung ausgelassen, Abschnitte ohne Inhalt (Register/Steuern, Vertretung) entfallen, ohne Rechtsform steht keine leere Klammer; Platzhalter bleiben sichtbar und hervorgehoben

### Changed (Frontend – M76 Tests unabhaengig von legal/operator.ts)
- `src/test/setup.ts` ersetzt `legal/operator` in allen Tests durch eine Fixture (brand "Astra", jurisdiction "DE", Platzhalter); die Suite ist damit gruen, egal welche echten Betreiberdaten eingetragen sind. `legal/operator.test.ts` prueft nur die Form der echten Datei. Regel in `docs/ui-conventions.md`

### Added (Frontend – M75 konfigurierbare Marke)
- `OPERATOR.brand` in `legal/operator.ts` (Standard "Astra"): der Markenname erscheint in der Logo-Wortmarke (Symbol bleibt), im Tab-Titel (Muster "Seite · Marke"), in der Landingpage (Titel, Kopf, Fussnote), in der Anmelde-/Registrierkarte und in allen Texten mit festem "Astra" (neuer Platzhalter `{brand}`, in jedem i18n-Text verfuegbar), im Dateinamen der Recovery-Codes und im `<title>` von `index.html` (Build-Zeit ueber ein Vite-Plugin aus `operator.ts`). "Astra" bleibt der Name der Software; Domain-Beispiele (`node01.astra.dev`) und interne Bezeichner bleiben unveraendert

### Fixed (Backend – M75)
- `MFA_ISSUER_NAME` wirkt jetzt: der Authenticator-Eintrag nutzt die Variable statt eines fest verdrahteten Namens. Standard bleibt „Astra Panel“ (bestehende Einträge ändern sich nicht); der Wert folgt bewusst nicht `SITE_NAME` und ist vor dem ersten Kunden zu setzen

### Added (Deployment – M75 Weiterleitungs-Domains)
- `REDIRECT_DOMAINS` (kommagetrennt, leer = aus): `scripts/deploy.sh` erzeugt aus `deploy/redirect.caddy.template` die Caddy-Site `deploy/sites/redirect.caddy` (ein Site-Block mit allen Domains, eigenes Zertifikat je Domain, `redir https://PANEL_DOMAIN{uri} permanent` = 301 mit Pfad und Query); Einträge werden geprüft (nur Domainnamen, nicht `PANEL_DOMAIN`/`NODE_DOMAIN`). `scripts/smoke-test.sh` prüft mit `REDIRECT_DOMAINS=…` je Domain 301 und `Location`. Runbook: Abschnitt „Weiterleitungs-Domains“ mit DNS-Tabelle

### Added (Backend – M75 Markenname)
- `SITE_NAME` (Standard „Astra“, max. 60 Zeichen, im Produktions-Check KRITISCH bei Überlänge oder Steuerzeichen) und `MAIL_FROM_NAME` (leer = `SITE_NAME`): alle Mail-Betreffe („Astrahost: …“, Platzhalter `{site}` in den Nachrichtenvorlagen), Absendername („Name <adresse>“, Zeilenumbrüche werden entschärft; enthält `MAIL_FROM` schon einen Namen, bleibt er), Admin-Alerts und CLI-Testalert. Der Rechnungskopf zeigt den Markennamen als erste Zeile, wenn er vom Standard abweicht; der Name steht im Beleg-Schnappschuss (`site_name`), Gutschriften übernehmen ihn von der Rechnung

### Added (Backend – M74 Schweiz-Tauglichkeit)
- `INVOICE_COUNTRY` (`DE`|`CH`, Standard `DE`; unbekannter Wert ist im Produktions-Check KRITISCH). Der Schnappschuss jeder Rechnung/Gutschrift hält `country`, Belege ohne Feld gelten als Deutschland; ein späterer Wechsel ändert alte Belege nicht
- CH: Standardhinweis „Nicht mehrwertsteuerpflichtig (Art. 10 Abs. 2 lit. a MWSTG)“ / „Not subject to Swiss VAT (Art. 10 para. 2 lit. a VAT Act)“, Beschriftung „MWST“/„VAT“ und „MWST-Nr.“/„VAT no.“; ein gesetzter `INVOICE_SMALL_BUSINESS_NOTE` gilt weiter in beiden Sprachen (Standardwert der Config ist jetzt leer)
- CHF-Betragsformat in Mails und Belegen: DE `CHF 1'234.56`, EN `CHF 1,234.56`; CSV-Export unverändert (reine Zahlen)
- Docs: Beispielblock in `.env.prod.example`, `docs/deploy-runbook.md` Abschnitt 9b „Betrieb in der Schweiz“, `docs/known-limitations.md`

### Added (Frontend – M74 Schweiz-Tauglichkeit)
- Rechtstexte umschaltbar ueber `OPERATOR.jurisdiction: "DE" | "CH"` in `legal/operator.ts` (Standard "DE", Texte unveraendert). Bei "CH": Impressum heisst "Anbieterkennzeichnung / Kontakt" (Angaben nach UWG Art. 3 Abs. 1 lit. s, keine TMG-/DDG-Bezuege), Datenschutzerklaerung nach dem Schweizer DSG (Verantwortlicher, Zwecke, Empfaenger inkl. optionalem Captcha-Dienst, Bekanntgabe ins Ausland, Aufbewahrung 10 Jahre nach Art. 958f OR, Rechte, Hinweis auf den EDOEB, DSGVO-Absatz fuer EU-Kunden), AGB mit Schweizer Recht und Gerichtsstand am Sitz des Betreibers und ohne Widerrufsrecht; im Shop erscheint vor dem Kauf der Hinweis, dass die Leistung sofort beginnt. Alle Fassungen DE/EN, Platzhalter und Pruefhinweis ("keine Rechtsberatung") bleiben; der Inhalt der Rechtstexte liegt in `legal/content.tsx`
- Geldformat: CHF wird mit Schweizer Locale formatiert ("CHF 1’234.56", en-CH in der englischen Oberflaeche), EUR/USD unveraendert; `/datenschutz` ist Teil der automatischen Barrierefreiheitspruefung

### Changed (Backend – M73 Erstattungen)
- Umsatzstatistik: `refunded_cents_by_currency` ist die Summe der Gutschriften im Zeitraum; kumulierte Teilerstattungen werden nicht mehr mehrfach gezaehlt (nur Erstattungs-Events vor M70 ohne `credit_note` zaehlen wie bisher)
- Verlorener Zahlungsstreit (`charge.dispute.closed`, Status `lost`) stellt eine Gutschrift ueber den Streitbetrag aus (hoechstens bis zum Rechnungsbetrag, idempotent je Event); `order:disputed` traegt die Nummer in `credit_note`

### Changed (Frontend – M72 Fehlertexte in der Nutzersprache)
- Jeder API-Aufruf sendet `Accept-Language: de|en` (Sprache der Oberflaeche). Fehlerdarstellung: der Server-Text gewinnt, nur technische Statuscodes ("Request failed: 500") und Netzwerkfehler kommen aus der Frontend-Uebersetzung; die ASCII-Umlaut-Korrektur alter deutscher Meldungen gilt nur noch in der deutschen Oberflaeche. Sonderfaelle (`manual`, `captcha_failed`, `rate_limited`, `reminder_cooldown`, `invalid_locale`, `email_not_verified`) werden am `code` bzw. Status erkannt, nicht am Text (Registrierung deaktiviert: Status 403/404)

### Added (Frontend – M70 Rechnungen)
- Konto: Abschnitt "Rechnungsadresse" (Name/Firma, mehrzeilige Anschrift, optional, "Erscheint auf deinen Rechnungen") ueber `PATCH /client/account`; wird ausgeblendet, wenn das Backend die Felder nicht liefert
- Bestellungen: Belegliste nennt "Rechnung" bzw. "Gutschrift" (mit Verweis "zu Rechnung ...", falls `references_number` in der Uebersicht steht), der Dialog traegt den passenden Titel und Dateinamen (`rechnung-...`/`gutschrift-...`); der Hinweis "Vereinfachter Zahlungsbeleg" erscheint nur noch bei Belegen ohne `kind`
- Admin: neue Seite "Rechnungen" (Verkauf) mit Monatsauswahl, Tabelle (Nummer, Art, Datum, Kunde, Netto, USt., Brutto, Waehrung; mobil als Karten) aus `GET /admin/invoices?format=json` und CSV-Download (`format=csv`, Blob). `/account` und `/admin/invoices` sind Teil der automatischen Barrierefreiheitspruefung

### Added (Frontend – M71 Registrierungsschutz)
- Registrierung und "Passwort vergessen" laden `GET /auth/captcha` (404/Netzfehler = kein Captcha) und rendern bei Turnstile/hCaptcha das Widget; das Script wird nur dann und nur von `challenges.cloudflare.com` bzw. `js.hcaptcha.com` geladen (Theme aus `data-theme`, Sprache aus `astra_lang`), ohne Anbieter gibt es keinen externen Aufruf. Das Token geht als `captcha_token` in den Body, nach einem Fehlversuch wird das Widget zurueckgesetzt. Datenschutzhinweis unter dem Formular (Text in `legal/captcha.ts` anpassbar)
- Honeypot-Feld `website` (ausserhalb des Bildschirms, nicht per Tab erreichbar, `aria-hidden`); ist es gefuellt, wird nichts gesendet
- 429 `rate_limited` bei Registrierung, Login und Passwort-Reset: "Zu viele Versuche, bitte in N Minuten erneut", Button so lange gesperrt (`ApiError.data.retry_after_seconds`); `captcha_failed` (400) und `captcha_unavailable` (503) mit eigenen Hinweisen. `/register` ist Teil der automatischen Barrierefreiheitspruefung

### Added (Frontend – M69 Zahlungserinnerung, vorbereitet)
- "Erinnerung senden" je Bestellung (active/past_due/pending_payment) auf der Admin-Bestellseite und bei den bald ablaufenden Bestellungen in der Admin-Uebersicht: `POST /admin/orders/<uuid>/remind`; 200 -> "Erinnerung gesendet", 429 `reminder_cooldown` -> "wieder moeglich in N h" (aus `retry_after_seconds`), 409 -> Button ausgeblendet. `ApiError.data` enthaelt die rohe Fehlerantwort

### Added (Frontend – M68)
- Admin-Uebersicht, "Auffaellige Zahlungen": Spalte "Betrag" (Monospace, `formatMoney`, "–" bei null), nur wenn das Backend `amount_cents`/`currency` am Zahlungsereignis liefert

### Added (Frontend – M67 Sprache fuer Mails und Belege)
- Beim Registrieren wird die aktuelle UI-Sprache als `locale` mitgesendet; nach dem Login wird eine am Konto gespeicherte Sprache uebernommen (null/fehlend: Auswahl des Browsers bleibt). Beim Umschalten im Nutzermenue oder unter Konto wird zusaetzlich `PATCH /client/account {locale}` gesendet (nur angemeldet, Fehler still ignoriert, auch bei Backend ohne das Feld). Kontoseite: Hinweis "Mails und Belege kommen in dieser Sprache"

### Added (Frontend – M65/M66)
- Admin-Bestellungen: Suchfeld (verzoegert ~300 ms, `?q=` in der URL, Escape/Leeren-Button, "Keine Treffer fuer ...") ueber `GET /admin/orders?q=`
- Admin-Uebersicht: Umsatz-Kachel mit Trend je Waehrung zum gleich langen Vorzeitraum ("+12 % zum Vorzeitraum", gruen/rot ueber Tokens); nur bei Vorzeitraum > 0, sonst "kein Vergleich", bei Backend ohne `prev_*` keine Trendzeile

### Added (Frontend – D11)
- `frontend/e2e/a11y.mjs`: automatische Barrierefreiheitspruefung mit axe-core (devDependency, kein CDN) gegen Preview und echtes Backend: Landing, Login, Dashboard, Shop, Bestellungen, Server-Detail, Admin-Uebersicht, Admin-Bestellungen, dunkel/hell, 390/1100 px; Verstoesse (WCAG A/AA) oder horizontales Scrollen beenden den Lauf mit Exit 1. Laeuft in `e2e/run-local.sh` nach `flow.mjs` und im Workflow `e2e.yml` (jetzt auch bei Aenderungen an `frontend/src/**` und den Tokens); gemeinsame Helfer in `e2e/lib.mjs`
- `docs/ui-conventions.md` neu: Checkliste fuer Seiten, Tokens/`sync:tokens`, `ui.css`-Bausteine, Status-Regeln, i18n-Namespaces und Plural-Konvention, Theme, Mobil-Regeln, bewusst nicht uebernommene Mockup-Inhalte

### Changed (Frontend – D10 Restmigration)
- Alle Komponenten und Seiten nutzen direkte Tokens; die Kompatibilitaets-Aliase (`--bg-page`, `--fg`, `--c-*`, `--tint-*` …) sind aus `theme.css` entfernt
- Uebersetzt (DE/EN): Transfer- und Loeschformular, Billing-Tick-Karte, offene Bestellungen, SFTP-Kopierbuttons, Validierungsmeldungen fuer Agents und Portbereiche, die gesamte Admin-Uebersicht (Plural sauber ueber `Intl.PluralRules`)
- Performance: Server-Detail, Konto, SSH-Keys und Rechtstexte werden per `React.lazy` nachgeladen (Haupt-Chunk 541 kB -> 441 kB); Dashboard, Shop, Bestellungen und Landing bleiben im Haupt-Chunk

### Changed (Frontend – D9 Admin-Seiten)
- Admin Bestellungen, Agents, Fleet Monitoring, Instances, Blueprints (inkl. Import), Produkte, Jobs, System und Webhooks im neuen Look-and-Feel und vollstaendig DE/EN (Namespaces `aorders`, `aagents`, `ainst`, `asys`). Tabellen sind mobil Karten (`tbl-cards` mit `data-label`), Formulare in `.panel`/`.field`, Fehler als `role=alert`, Loeschen/Rotieren mit Bestaetigung, Secrets nie in Labels
- Bestellungen: Statusfilter und Dialog "Als bezahlt markieren" mit Zahlungsreferenz, vorbelegt mit dem Verwendungszweck (`payment_purpose`)
- Gemeinsame Komponenten `ErrorState`, `EmptyState`, `LoadingState`, `ConfirmButton`, `AutoRefreshToggle`, `OrderNotice` auf `ui.css`-Klassen und Tokens (keine Emojis, keine alten Farb-Aliase); Icons Papierkorb, Stift, Speichern
- Bekannt: `TransferInstanceForm`, `DeleteInstanceForm`, `UtilizationBar`, `SftpAccess`, `ReceiptViewer` u. a. nutzen noch alte Farb-Aliase und teils feste deutsche Texte; Validierungsmeldungen in `lib/agentForm.ts` und `lib/portRange.ts` sind deutsch. Eine Admin-Nutzerseite gibt es nicht

### Changed (Frontend – D8b Server-Unterkomponenten)
- Konsole, Dateien, Backups, Routinen, Mitbenutzer und Aktivitaet im neuen Look-and-Feel (nur Tokens und `ui.css`-Klassen, keine Emojis, Icon-Buttons mit `aria-label`, Tabellen mit `scope=col`, Fehler `role=alert`), funktionsgleich; alle Texte DE/EN (Namespaces `sconsole`, `sfiles`, `sbackups`, `sroutines`, `susers`). Konsolenzeilen tragen ihre Art (`kind`) statt eines Textpraefixes, die Farbe haengt nicht mehr am uebersetzten Text. Neue Tests je Komponente. Toast auf direkte Tokens umgestellt
- Nicht uebersetzt bleiben Texte vom Server (Backup-/Restore-Antworten, Aktivitaets-Ereigniscodes und -beschreibungen). Farbige Ereignis-Badges im Aktivitaetslog entfallen (neutrales Badge)

### Added (Frontend – M64-Nachtraege)
- Spielname und Verwendungszweck aus M64: Unterzeile "Spiel · Paket" an Server- und Bestellkarten (ohne Spielname nur das Paket), Verwendungszweck (`payment_purpose`, Monospace mit Kopieren-Button) in der Dashboard-Bestellkarte bei offener Ueberweisung, neben dem Zahlungshinweis auf der Bestellungen-Seite und als Zeile in der Admin-Bestellliste

### Added (Frontend – D7 Landingpage)
- Oeffentliche Startseite `/` nach `design/mockups/Landing.html` (ausgeloggt; angemeldet zeigt `/` weiter das Dashboard "Meine Server"): Kopf mit Logo, Anker-Navigation und "Anmelden"/"Jetzt bestellen" (mobil Menue), Hero, Pakete aus `GET /api/client/products` (Preis, RAM/CPU, Speicher, Spiel; "Jetzt bestellen" fuehrt zu `/shop?plan=<id>` und waehlt das Paket vor), Spiele nur aus den Blueprint-Namen der Pakete, "So funktioniert's" passend zum Zahlungsweg, Fuss mit Rechtslinks und Sprachumschalter. DE/EN. Der Shop liest `?plan=` zur Vorauswahl
- Aus dem Mockup bewusst nicht uebernommen, weil nicht belegbar: "Server in Deutschland", "Taegliche Backups", Spielerzahlen, Backup-Anzahl je Paket, "Beliebt"-Marke, MwSt-Hinweis, feste Spieleliste. Die Ueberschrift "In drei Minuten online" ist Mockup-Text und vom Betreiber zu bestaetigen

### Changed (Frontend – D6 Admin-Uebersicht nach Mockup)
- `/admin` nach `design/mockups/AdminOverview.html`: Warnbanner (rot, role=alert) bei nicht erreichbaren oder beeintraechtigten Nodes mit Heartbeat und betroffenen Instances, gebuendelter Hinweis (role=status) zu Zahlungen mit Fehlstatus, in 24 h ablaufenden Bestellungen, ausfallendem Abrechnungs-Tick und zu lange wartenden Bestellungen; vier Kennzahlen (Umsatz exakt aus `stats/revenue` mit Rueckfall, Bestellungen im Zeitraum mit bezahlt/wartend/ueberfaellig, laufende Instances aus `GET /admin/instances`, Abrechnungs-Tick); Zeitraum waehlbar (7/30/90 Tage); Node-Auslastung mit RAM-/Festplattenbalken (Warnfarbe ab 80 %, "ueberbucht" mit schraffiertem Anteil, kein Limit/keine Daten) und Tabelle der auffaelligen Zahlungen (`payment-events`); Aktualisierung alle 30 s, jede Quelle faellt einzeln aus
- Nicht aus den APIs verfuegbar und daher weggelassen: Trend "+12 % zum Vormonat", Betrag je Zahlungsereignis, naechster Tick-Lauf, "Erinnerung senden"
- Status-Badge: "nicht erreichbar" ist rot

### Changed (Frontend – D5 Server-Detail)
- Server-Detailseite nach Mockup: Zurueck-Link "Meine Server", Titel mit Status-Badge und Kurz-ID, Start/Neustart/Stop/Kill im Seitenkopf (passend zum Container-Zustand; Kill mit Rueckfrage), Tabs Konsole / Dateien / Backups / Einstellungen (Tastatursteuerung, Tab in der URL `?tab=`), rechts Infospalte mit Verbindung (Adresse, IP, Node), Ressourcen (Balken fuer CPU, RAM, Festplatte, Netzwerk, Uptime; ab 80 % Warnfarbe) und Laufzeit (Paket, Laufzeitende, Verlaengerungspreis, "Verlaengern"; nur mit zugehoeriger Bestellung). Einstellungen enthalten Variablen, SFTP-Zugang, Routinen, Mitbenutzer, Aktivitaet, Details, Limits und "Server loeschen". Seitentexte DE/EN; die Unterkomponenten (Konsole, Dateien, Backups, Routinen, Mitbenutzer) bleiben deutsch

### Changed (Frontend – D4 Shop "Neuer Server")
- Shop nach Mockup: nummerierte Schritte (1 Paket als Auswahlkarten mit Preis und Ressourcen, 2 Servername, 3 Zahlungsweg), Zusammenfassung rechts (mobil darunter), `inputStyle` und Eingabefelder nach Design. Der Zahlungsweg kommt aus `GET /api/client/billing-info`: bei Online-Zahlung "Weiter zur Zahlung" (Bestellung anlegen, dann direkt zum Checkout; bei Fehler bleibt die Bestellung offen und ist unter Bestellungen bezahlbar), bei Ueberweisung "Verbindlich bestellen" mit Hinweistext des Betreibers, kostenlose Pakete ohne Zahlungsschritt. Nicht angeboten, weil das Backend es nicht kennt: Spielauswahl (ein Paket gehoert zu genau einem Blueprint), Standort, Wechsel zwischen Paketen, MwSt-Angabe

### Changed (Frontend – D3 Kunden-Dashboard "Meine Server")
- Dashboard nach Mockup: Titel "Meine Server" mit Untertitel "N Server · M laufen", Primaerbutton "Neuer Server" (mobil 44-px-Icon-Button), Hinweisbanner fuer offene Zahlungen ("Zahlungsdaten anzeigen" bzw. "Jetzt mit Karte bezahlen"), Serverkarten im Grid (Adresse in der Konsolen-Zeile mit Kopieren, Zeilen nur aus echten Daten: RAM, Speicher, Laufzeitende aus der Bestellung, bald faellig in Warnfarbe mit "Verlaengern"; Aktionen Stop/Start/Neustart/Oeffnen ueber die Power-API), Karten fuer Bestellungen ohne Server (wartet auf Zahlung/Platz) mit Stornieren, gestrichelter Leerzustand, Fussnote
- Status-Badge einheitlich nach Design (Punkt + Text, --surface-2, 1 px --border), Buttons mobil mit 44-px-Touch-Zielen; Bausteine in `src/styles/ui.css`
- Nicht aus der API verfuegbar und daher nicht angezeigt: Spieler, RAM-Auslastung, Spielname, Verwendungszweck der Ueberweisung

### Changed (Frontend – D2 App-Shell)
- Neue App-Shell nach `design/mockups`: Seitenleiste links (240 px, einklappbar auf 56 px nur Icons mit `aria-label`/`title`, Zustand in localStorage), Logo (SVG-Stern in `--accent`, Satellit in `--text`), Navigation mit Icon + Text und aktivem Eintrag in `--accent-soft` (laengster Pfadpraefix), Admin-Gruppen nur fuer Admins, unten Nutzermenue (Avatar-Initialen, Sprache, Design, Konto, Abmelden). Mobil ab 760 px: Kopfzeile mit Logo, Avatar und 44-px-Hamburger sowie Vollbild-Overlay-Menue. Seitenkopf mit Titel, optionalem Untertitel und Aktionen (`PageLayout` Props `subtitle`, `actions`). Skip-Link und Tab-Titel bleiben; Sprachumschalter in der Fusszeile nur noch ausgeloggt
- Design-Darstellung im Konto: "Wie das Geraet" heisst jetzt "System"

### Changed (Frontend – D1 Design-Tokens)
- `design/tokens.css` ist die Quelle der Farben, Schrift und Maße; `frontend/src/styles/tokens.css` ist eine Kopie (Docker-Build-Kontext ist `frontend/`), `npm run sync:tokens` aktualisiert sie, ein Test prueft die Gleichheit. `src/theme.css` bindet sie ein und liefert Kompatibilitaets-Aliase fuer die bisherigen Variablennamen. Dunkel ist Standard, hell ueber `data-theme="light"`; `lib/theme.ts` setzt `data-theme` immer explizit (System-Praeferenz wird erkannt und verfolgt)
- Schrift Geist / Geist Mono selbst gehostet (`@fontsource/geist`, `@fontsource/geist-mono`, nur Latin-Subsets, kein externer Abruf wegen DSGVO)
- Alle verbliebenen Hex-Werte im Komponenten-Code durch Tokens ersetzt (Buttons, Power-Buttons, Server-Konsole, Dateimanager u.a.); Buttons nach DESIGN.md (36 px, Radius 6, Gewicht 500)
- WCAG-AA-Korrekturen in `theme.css` (axe fand sie in den Tokens: u.a. `--text-3` hell 4,36:1, Gefahr-Button dunkel mit weissem Text 3,35:1), zur Uebernahme in `design/tokens.css` vorgeschlagen

### Changed (Frontend – Umsatz-Kachel auf `GET /api/admin/stats/revenue`)
- Admin-Uebersicht: Umsatz der letzten 30 Tage exakt aus den Belegen (je Waehrung, Zahlungen davon Verlaengerungen, "Erstattet im Zeitraum: X (nicht abgezogen)"); bei 404 (aelteres Backend) Rueckfall auf die bisherige Schaetzung aus der Bestellliste mit Hinweis

### Added (Frontend – F7 Zahlungsbelege, M62)
- Kunden-Bestellungen: pro Bestellung die Belege (Nummer, Datum, Betrag) mit "Anzeigen"; der Beleg wird per fetch mit Token geholt (`GET /api/client/orders/{uuid}/receipt?number=&format=html`) und in einem Dialog mit sandbox-Iframe (ohne Skripte) angezeigt, "Als Datei speichern" laedt ihn als HTML herunter. Hinweis "Vereinfachter Zahlungsbeleg, keine Rechnung mit Umsatzsteuer." Admin-Bestellliste zeigt die Belegnummern als Text

### Added (Frontend – F6 MFA-Recovery-Codes, M60)
- Nach dem MFA-Setup werden die 10 Recovery-Codes gross angezeigt (Kopieren, "Als Textdatei speichern"); geschlossen wird erst nach der Bestaetigung "Ich habe die Codes gesichert". Konto: Anzeige "noch N von 10", Warnung bei wenigen/keinen Codes, "Neue Codes erzeugen" mit Passwortabfrage (falsches Passwort = 403 `invalid_password`, die Anmeldung bleibt bestehen)
- Login im MFA-Schritt: Umschalter "Recovery-Code verwenden" (Textfeld statt Ziffernfeld, dasselbe Feld `mfa_code`); nach Nutzung eines Codes einmaliger Hinweis "noch N uebrig", bei N <= 2 als Warnung mit Link ins Konto (`FlashBanner`, `lib/flash.ts`)

### Changed (Frontend – M61 Logout)
- Der Abmelden-Button sperrt das Token zuerst serverseitig (`POST /api/auth/logout`, best effort, Fehler werden ignoriert) und meldet danach immer lokal ab; der 401-Handler ruft den Endpunkt bewusst nicht auf

### Added (Frontend – F5 Englische Sprachversion)
- Leichtgewichtiges i18n (`src/i18n`): Deutsch bleibt Standard, Englisch ist per Sprachumschalter (Fusszeile jeder Seite, inkl. Login, und Konto > Darstellung) waehlbar und wird im Browser gemerkt (`astra_lang`). Woerterbuecher `de`/`en` je Namensraum, der Compiler erzwingt gleiche Schluessel, ein Test prueft Platzhalter-Paritaet. Uebersetzt: Login, Registrierung, Passwort-Reset, E-Mail-Bestaetigung, Navigation, Dashboard, Shop, Bestellungen (inkl. Status, Hinweise, Verbindungsadresse), Konto (Passwort, MFA, API-Keys, Darstellung), SSH-Keys, 404, Fehlerseiten, Zeitangaben, Datums- und Waehrungsformate (`en-GB`)
- Nicht uebersetzt (bewusst/spaeter): Admin-Bereich, Server-Detailseite (Konsole, Dateien, Backups), Rechtstexte (Impressum, Datenschutz, AGB) sowie Meldungen, die das Backend selbst liefert (deutsch)
- Konto: Hinweis zum Passwortwechsel korrigiert (seit M57 werden andere Geraete abgemeldet)
- Test `OrdersPage` (Rueckkehr von Stripe) war ein Race und ist stabil

### Added (Frontend – Erstattungen und Zahlungsstreit, M59)
- Bestellungen: Status `refunded` ("Erstattet", rot) und Felder `refunded_at`/`disputed`; Admin-Statusfilter "Erstattet"; Hinweis "Zahlung erstattet am …, der Server wird am … gelöscht" in Kunden- und Admin-Liste, Badge "Zahlung angefochten" bei offenem Zahlungsstreit; erstattete Bestellungen zaehlen nicht zum Umsatz der Admin-Uebersicht

### Added (Frontend – F4 Dunkler Modus)
- Farb-Tokens als CSS-Variablen (`src/theme.css`), alle bisher hartkodierten Farben der Seiten und Komponenten (Karten, Tabellen, Status-Badges, Banner, Auslastungsbalken) darauf umgestellt; dunkles Design folgt `prefers-color-scheme: dark` und ist im Konto unter "Darstellung" auf Hell/Dunkel/Wie das Gerät umschaltbar (im Browser gemerkt, ohne Aufblitzen beim Laden). Textfarben im Dunkeln erfuellen WCAG AA: alle 16 Routen im dunklen Design per axe geprueft (0 Verstoesse). Server-Konsole bleibt bewusst dunkel

### Added (Frontend – F3 E2E-Durchlauf)
- `frontend/e2e/`: Playwright-Durchlauf gegen das echte Backend (SQLite, Stub-Runner, manuelle Zahlung): Registrierung, Login, Bestellung im Shop, Admin markiert als bezahlt, Kunde sieht den Server im Dashboard. `./e2e/run-local.sh` startet Backend und Frontend, fuehrt den Durchlauf aus und raeumt auf (Anleitung in `frontend/e2e/README.md`); `.github/workflows/e2e.yml` fuehrt ihn manuell bzw. bei Aenderungen an den E2E-Dateien aus (lokal verifiziert, auf GitHub noch nicht)
- Login-Seite: Feldbezeichnung "Benutzername oder E-Mail" statt "Username oder Email"

### Changed (Frontend – F2 Admin-Seiten vereinheitlicht)
- Alle 16 Routen bei 390 und 1100 px per Browser-Sweep geprueft (Tab-Titel, kein horizontaler Seitenueberlauf, axe WCAG 2 A/AA ohne Verstoesse, kein Absturz). Behoben: Kontrast der Event-Chips in Webhooks und der Auswahlzaehler im Dateimanager, Tabellen-Scrollbereiche der Admin-Seiten sind per Tastatur erreichbar (`ScrollRegion`). Keine Funktionsaenderung

### Added (Frontend – F1 Admin-Uebersicht)
- Neue Seite `/admin` ("Uebersicht", Navigationspunkt fuer Admins): Kacheln Umsatz der letzten 30 Tage (Naeherung aus `paid_at`/`price_cents` von `GET /api/admin/orders`, clientseitig je Waehrung aggregiert), Bestellungen je Status (pending_payment, awaiting_provisioning, active, past_due, verlinkt auf die gefilterte Liste), Node-Auslastung (aus `GET /api/admin/agents/monitoring`, effektive Kapazitaet inkl. Ueberallokation, Agents ohne Limit ausgewiesen), Billing-Tick und Zahlungsereignisse mit Status `mismatch`/`unapplied` (`GET /api/admin/payment-events`). Jede Kachel faellt einzeln aus; Aktualisierung alle 60 s; mobil einspaltig
- `formatTimeAgo`: "vor 1 Tag" statt "vor 1 Tagen"

### Added (Frontend – Betrieb, Barrierefreiheit)
- Admin-Seiten werden per Code-Splitting nachgeladen (Haupt-Bundle ca. 452 -> 385 KB); fehlt nach einem Deployment eine Seiten-Datei, zeigt die App "Neue Version verfuegbar" mit Reload-Button statt der allgemeinen Fehlerseite
- Browser-Tab-Titel folgt der Seite ("Meine Bestellungen - Astra"); Skip-Link "Zum Inhalt springen" fuer Tastaturnutzer
- Admin-System: Karte "Billing-Tick" (Ampel, letzter Lauf relativ, Bestellungen je Status, Warnung "Container billing pruefen"); bezahlte Bestellungen ohne freien Node mit Warnung "Kapazitaet pruefen". Auf dem Admin-Dashboard erscheint die Karte nur bei Stoerung
- Bestellungen: Nach der Stripe-Rueckkehr Hinweis auf die Bestaetigungsmail (M54)

### Added (Phase 2 – Produktions-Deployment)
- GitHub Actions `.github/workflows/backend.yml`: alle Testskripte plus Migrations-Roundtrip auf SQLite bei Push/PR
- `POST /api/client/orders/{uuid}/checkout`: 409-Antworten tragen `code` (`manual`, `invalid_status`), `PaymentError.code`
- `docker-compose.prod.yml`: Container `billing` fuehrt `cli.py billing-tick` alle `BILLING_TICK_INTERVAL` Sekunden (Standard 300) aus; `BILLING_GRACE_DAYS` in `.env.prod.example`
- `POST/PATCH /api/admin/agents`: Kapazitaetsfelder `memory_total`, `disk_total`, `cpu_total` und `*_overalloc` pflegbar (Ganzzahl >= 0, 0 = kein Limit)
- `docker-compose.prod.yml`: Caddy als TLS-Terminierung (Let's Encrypt, einziger oeffentlicher Eingang 80/443),
  Worker-Container fuer die Redis-Job-Queue, Healthchecks fuer Backend/Redis, Redis mit Passwort und AOF,
  gemeinsamer Backend-Env-Block (`x-backend-env`), kein direktes Port-Mapping fuer Frontend/Backend mehr
- `deploy/Caddyfile` + `deploy/node.caddy.template`: optionaler Reverse Proxy fuer den Wings-Node auf
  demselben Host (`NODE_DOMAIN` -> `host.docker.internal:8080`, Websockets inklusive)
- `.env.prod.example` im Root (Domains, Secrets, Admin, Mail, Queue), `COMPOSE_FILE` vorbelegt
- `scripts/deploy.sh` (Build, Start, Warten auf Readiness, `--bootstrap`, `--status`),
  `scripts/install-wings.sh` (Docker + Wings + config.yml aus dem Panel + systemd, `--pelican`),
  `scripts/smoke-test.sh` (Health, TLS, Admin-Guard, Remote-API-Auth je Agent)
- `docs/deploy-runbook.md`: Runbook fuer Panel + Wings auf einem Server, Abnahme-Checkliste, Umzug

### Changed
- `frontend/nginx.conf`: `X-Forwarded-Proto` wird vom vorgelagerten Proxy durchgereicht (statt `$scheme`),
  damit das Backend hinter Caddy `https` erkennt; Backend nutzt `PROXY_FIX_X_FOR/X_PROTO=2`
- `cli.py db-init` (neu) ersetzt `flask db upgrade` im Entrypoint: frische Datenbank -> `create_all()` +
  `stamp head`, bestehende Datenbank -> `upgrade`. Die Migrationen legen die Basistabellen nicht selbst an,
  ein `flask db upgrade` auf leerer DB brach bisher mit "relation instances does not exist" ab
- `requirements.txt`: SQLAlchemy auf 2.0.54 gepinnt

### Fixed (gegen echtes PostgreSQL 16 und SQLite verifiziert)
- PostgreSQL-URLs werden auf den psycopg2-Treiber normalisiert (`postgresql://` -> `postgresql+psycopg2://`).
  Mit SQLAlchemy >= 2.1 waere sonst psycopg v3 der Default und der Start schlug mit
  `ModuleNotFoundError: psycopg` fehl
- Migration `k1f2g3h4i5j6` (M29 Suspension) brach auf SQLite im Batch-Modus mit "Constraint must have a name"
  ab; jetzt `ALTER TABLE ADD COLUMN` ohne Neuaufbau (FK-Constraint nur auf PostgreSQL)
- Migration `l2g3h4i5j6k7` (M33) nutzt fuer `agents.uuid` einen Unique-Index statt einer Batch-Constraint
  (gleicher SQLite-Fehler)
- Downgrades von M29/M33/M38 tolerieren jetzt Datenbanken, deren Schema per `db-init`/`create_all()`
  entstand (andere Constraint-Namen als im Migrationspfad). Up-/Downgrade-Roundtrip von Head bis M28 und
  zurueck auf PostgreSQL 16 und SQLite verifiziert, jeweils fuer Migrations- und create_all-Datenbanken

### Security (M35 – Admin-Guard)
- Der gesamte `/api/admin`-Blueprint verlangt jetzt einen angemeldeten Admin (`before_request`, JWT, API-Key oder in Dev/Test `X-User-Id`). Ausnahme: `GET /api/admin/health`. Ohne Login 401, ohne Admin-Recht 403
- Schalter `ADMIN_GUARD_ENABLED` (Standard `true`), nur in `TestingConfig` aus, damit die Legacy-Tests M10–M32 ohne Auth weiterlaufen
- `backend/test_m35.py` (20 Tests, prueft u.a. jede registrierte Admin-Route per Routentabelle)

### Added (M72 – Englische Fehlertexte der API)
- Kundenseitige Fehlerantworten (`/api/auth/*`, `/api/client/*`) sind einheitlich `{error, code}`; `error` in der Sprache des Aufrufers: angemeldeter Nutzer -> `users.locale`, sonst `Accept-Language` (de/en, nach q-Wert), sonst Deutsch (`app.i18n.request_locale()`). `code` ist stabil (vorhandene Codes bleiben, sonst Katalog, sonst nach HTTP-Status). Deutsch ist wortgleich zu heute
- Katalog `app/i18n/errors.py` (rund 150 Texte mit Code und englischer Fassung, Platzhalter, verschachtelte Texte) und ein `after_request`-Hook schreiben die Antworten um; die ausloesenden Stellen bleiben unveraendert. Texte ohne Eintrag (Wings-Meldungen, Sperrgruende) bleiben im Original. Admin-Routen und Webhooks bleiben deutsch
- `backend/test_m72.py` (74 Tests): Katalog-Integritaet, Abdeckung aller Fehlertexte im Quelltext per AST, `request_locale`, Stichproben ueber Auth- und Kundenrouten (en ohne Anmeldung, Nutzer-Locale gewinnt, Fallback), 429 lokalisiert, Admin deutsch, jede JSON-Fehlerantwort aller Kundenrouten hat `{error, code}`. Doku in `docs/orders-api.md` (Fehlerformat) und `docs/ui-conventions.md`

### Added (M70 – Rechnungen mit Umsatzsteuer statt einfacher Belege)
- Aus dem Zahlungsbeleg wird eine Rechnung (Kleinbetragsrechnung § 33 UStDV, bis 250 € brutto): `VAT_RATE` (Prozent, Standard `0` = Kleinunternehmer mit Hinweis `INVOICE_SMALL_BUSINESS_NOTE`, DE/EN), optional `INVOICE_SELLER_VAT_ID`. Preise sind Bruttopreise: netto = brutto / (1 + Satz), kaufmaennisch auf Cent gerundet, USt = brutto - netto, Summen aus den gerundeten Teilen. Der Schnappschuss haelt `vat_rate`, `net_cents`, `vat_cents`, `gross_cents`, `period_start`/`period_end` (Leistungszeitraum; bei wartender Bereitstellung "30 Tage ab Bereitstellung"), `seller {lines, vat_id}` und `customer_billing {name, address}` (nur wenn hinterlegt); eine spaetere Aenderung von `VAT_RATE` aendert alte Rechnungen nicht. Titel "Rechnung"/"Invoice", Netto/USt/Brutto-Block bzw. Kleinunternehmer-Hinweis, Empfaengerblock, Rechnungsnummer unveraendert aus `invoice_counters`
- Gutschrift bei Erstattung (M59): je Erstattungs-Ereignis ein Dokument `kind=credit_note` mit negativen Betraegen und eigener Nummer aus demselben Zaehler, `references_id` auf die Rechnung, "zu Rechnung Nr. ...", Steuersatz und Zeitraum der Rechnung; nur ueber den noch nicht gutgeschriebenen Rest (Stripe meldet kumuliert), idempotent. Event `order:refunded` nennt die `credit_note`-Nummer
- `users.billing_name` (200) und `users.billing_address` (500), `PATCH /api/client/account` und `User.to_dict`; Migration `y5t6u7v8w9x0` (zusaetzlich `receipts.kind`, `receipts.references_id`, Up/Down auf SQLite geprueft, auch ueber die ganze Kette)
- `GET /api/admin/invoices?from=&to=&format=json|csv` (Buchhaltungsexport, Standard laufender Monat; CSV mit Semikolon, UTF-8 BOM, Dateiname `rechnungen-JJJJ-MM.csv`, Formel-Zeichen entschaerft); `GET /api/admin/stats/revenue` zusaetzlich `net_by_currency` und `vat_by_currency`, Umsaetze zaehlen nur Rechnungen. `Order.receipts` (Kurzform) und das Dokument-JSON tragen `kind` und `references_number` (Gutschrift -> Rechnungsnummer, sonst null); Standardabruf von `/receipt` liefert die neueste Rechnung. Belege vor M70 rendern weiter als Zahlungsbeleg (Steuerfelder `null`). `backend/test_m70.py` (90 Tests), `test_m62`/`test_m67` auf die neue Darstellung angepasst; Doku in `docs/orders-api.md` (inkl. was nicht abgedeckt ist), `known-limitations`, Runbook (Steuerkonfiguration, Export), `.env.prod.example`

### Security (M71 – Registrierungsschutz)
- Rate-Limits je IP: Registrierung 5/Stunde, Login 10/Minute, Passwort-Reset-Anfrage 3/Stunde (`RATELIMIT_REGISTER_PER_HOUR`, `RATELIMIT_LOGIN_PER_MINUTE`, `RATELIMIT_PASSWORD_RESET_PER_HOUR`), uebrige Auth-Routen weiter `RATELIMIT_AUTH_PER_MINUTE`; Login-Kontosperre nach 20 Fehlversuchen/Stunde (`RATELIMIT_LOGIN_FAILURES_PER_HOUR`, Event `auth:login_blocked`). Antwort 429 `{error, code: "rate_limited", retry_after_seconds}` plus `Retry-After`; Limiter mit Fenstern in Stunden, Redis oder In-Memory, IP ueber ProxyFix (`PROXY_FIX_X_FOR`)
- CAPTCHA anbieterneutral (`CAPTCHA_PROVIDER` none/turnstile/hcaptcha, `CAPTCHA_SITE_KEY`, `CAPTCHA_SECRET`): `GET /api/auth/captcha` `{provider, site_key}`; `captcha_token` bei Registrierung und Passwort-Reset-Anfrage (fehlend/ungueltig 400 `captcha_failed`, Dienst nicht erreichbar 503 `captcha_unavailable`, Timeout 5 s); Honigtopf-Feld `website` bei der Registrierung (400 `invalid_request`); Produktions-Check warnt bei fehlenden Keys. `backend/test_m71.py` (54 Tests), Doku in `docs/operations.md` (Registrierungsschutz, Datenschutzhinweis) und Runbook

### Added (M69 – Manuelle Zahlungserinnerung)
- `POST /api/admin/orders/{uuid}/remind`: Admin schickt dem Kunden die zum Status passende Zahlungsmail in dessen Sprache (`active`: Erinnerung vor Laufzeitende, `past_due`: Zahlung ueberfaellig mit verbleibender Frist, `pending_payment`: neue Mail "Zahlung noch offen" mit Betrag und Verwendungszweck, DE/EN). Antwort `200 {sent_at, kind}`; 409 bei beendet/storniert/erstattet/wartend, kostenlos, gekuendigt oder ohne E-Mail (je mit `code`); 429 `reminder_cooldown` mit `retry_after_seconds` (hoechstens eine manuelle Erinnerung je Bestellung und 24 Stunden, gelesen aus dem Activity-Log, keine Migration). Event `order:reminder` mit `kind=manual` und Akteur. `BillingError` traegt optional `code` und Zusatzfelder, `_mail_order` liefert, ob gesendet wurde. `backend/test_m69.py` (28 Tests)

### Added (M68 – Betrag je Zahlungsereignis)
- `payment_events.amount_cents` und `payment_events.currency` (Migration `x4s5t6u7v8w9`, Inspector-Guard, Up/Down geprueft): Betrag laut Anbieter-Ereignis, bei `mismatch` der tatsaechlich gezahlte (nicht der erwartete) Betrag, bei Erstattungen der erstattete Betrag, bei Streitfaellen der angefochtene; NULL bei Altbestand und Ereignissen ohne Betrag. `GET /api/admin/payment-events` liefert beide Felder. Eine Wiederzustellung eines unfertigen Altereignisses zieht den Betrag nach. `backend/test_m68.py` (16 Tests)

### Added (M67 – Sprache des Kunden fuer Servertexte)
- `users.locale` (`de`/`en`, NULL = Deutsch; Migration `w3r4s5t6u7v8`, Inspector-Guard, Up/Down geprueft). `PATCH /api/client/account {locale}` (ungueltig: 400 `invalid_locale`), optionales `locale` bei der Registrierung, `locale` im Nutzerobjekt
- Neues Modul `app/i18n` (`tr(locale, key, **fmt)`, Fallback Deutsch, Betrags- und Datumsformat je Sprache): alle Kunden-Mails (Bestaetigung, Passwort-Reset, Zahlung, Server bereit, Verlaengerung, Erinnerung, Sperre, Loeschhinweis, Beendet, Erstattung, Recovery-Code) und die Zahlungsbelege werden in der Sprache des Kunden gerendert. Deutsch unveraendert (bis auf das Betragsformat der Erinnerung: `4,99 EUR` statt `4.99 EUR`); Admin-Alerts, API-Fehlertexte und Activity-Beschreibungen bleiben deutsch. `backend/test_m67.py` (59 Tests, u.a. gleiche Schluessel und Platzhalter in DE und EN), Doku in `docs/orders-api.md` und `docs/ui-conventions.md`

### Added (M63 – Umsatzstatistik)
- `GET /api/admin/stats/revenue?days=30` (Admin-Guard, `days` 1 bis 365, sonst 400): Umsatz auf Basis der Zahlungsbelege (`receipts.issued_at`, M62): `{days, since, by_currency, paid_count, renewals_count, refunded_cents_by_currency}`. Erster Beleg einer Bestellung = Erstzahlung, weitere = Verlaengerungen; Erstattungen (Events `order:refunded`, M59) getrennt je Waehrung, nicht verrechnet. Gratis-Pakete und Zahlungen vor M62 fehlen, keine Waehrungsumrechnung. `backend/test_m63.py` (20 Tests)

### Added (M62 – Zahlungsbelege mit fortlaufender Nummer, Grundlage)
- Jede verbuchte Zahlung (nicht kostenlose Pakete) bekommt einen Beleg mit fortlaufender, lueckenloser Nummer je Jahr (`INVOICE_NUMBER_FORMAT`, Standard `AST-{year}-{seq:05d}`): Zaehler `invoice_counters` mit Zeilensperre (PostgreSQL), Zaehler und Beleg in einer Transaktion, Belege werden nie geloescht. Tabellen `receipts` und `invoice_counters` (Migration `v2q3r4s5t6u7`)
- `receipts: [{number, issued_at, amount_cents, currency}]` in den Bestellungen (Kunde und Admin); `GET /api/client/orders/{uuid}/receipt?number=&format=html|text|json` (HTML escaped, `nosniff`, CSP, `no-store`). Anbieter-Kopf und Fusszeile ueber `INVOICE_SELLER` und `RECEIPT_FOOTER`. Kein Steuerbeleg, kein PDF, keine Umsatzsteuer; Belege nur fuer Zahlungen ab M62. Ein Fehler beim Ausstellen blockiert die Zahlung nie. `backend/test_m62.py` (42 Tests); Doku in `docs/orders-api.md`, was fuer echte Rechnungen fehlt

### Security (M61 – Logout-Blocklist)
- `POST /api/auth/logout` sperrt das verwendete Access-Token (`jti`) bis zu seinem Ablauf: neue Tabelle `revoked_tokens` (Migration `u1p2q3r4s5t6`), `get_current_user` prueft die Sperre bei jedem Request (ein Primaerschluessel-Lookup). Antwort enthaelt `token_revoked` (false bei API-Key, Dev-Header oder Token ohne `jti`). Andere Tokens des Kontos bleiben gueltig; ein zweiter Logout mit dem gesperrten Token ist 401
- Aufraeumen: der naechste Logout loescht abgelaufene Eintraege beilaeufig, `python cli.py cleanup-jobs` (auch `--dry-run`) raeumt mit auf und meldet `revoked_tokens: {matched, deleted}`. Bewusst kein Redis (Neustart/Flush haette Abmeldungen aufgehoben). `backend/test_m61.py` (25 Tests)

### Security (M60 – MFA-Recovery-Codes)
- Beim Aktivieren von MFA entstehen 10 einmalige Recovery-Codes (`xxxxx-xxxxx`); gespeichert werden nur gesalzene Hashes (vorher 8 Klartext-Codes). Klartext nur in der Antwort von `POST /api/auth/mfa/verify`; Migration `t0o1p2q3r4s5` hasht vorhandene Klartext-Codes (bleiben gueltig)
- `POST /api/auth/mfa/recovery-codes` `{password}` erzeugt neue Codes (alte ungueltig; falsches Passwort 403 `invalid_password`, MFA aus 409). Login akzeptiert in `mfa_code` (oder `recovery_code`) TOTP oder Recovery-Code; Recovery-Login liefert `recovery_code_used` und `recovery_codes_remaining`, schickt dem Kontoinhaber eine Mail und das Event `auth:mfa_recovery_used`. `mfa_recovery_codes_remaining` in `/api/auth/me` und im `user`-Objekt
- Einmalnutzung per Zeilensperre (PostgreSQL). `backend/test_m60.py` (28 Tests), `test_m19.py` angepasst, Doku `docs/mfa-recovery-codes.md`

### Added (M59 – Stripe-Erstattungen und Zahlungsstreitigkeiten)
- Webhook wertet `charge.refunded`, `charge.dispute.created` und `charge.dispute.closed` aus (bestehender Pfad, gleiche Signatur und Idempotenz). Zuordnung ueber die Zahlungsreferenz (auch aeltere Verlaengerungen), ersatzweise `metadata.order_uuid`
- Volle Erstattung der letzten Zahlung: neuer Status `refunded` (Spalte `refunded_at`), Instance gesperrt (Grund "Zahlung erstattet"), nach `BILLING_GRACE_DAYS` loescht der Tick sie (`expired`); Teilerstattung oder aeltere Zahlung: nur Event und Alert. Streit eroeffnet: Flag `disputed_at`, Instance gesperrt ("Zahlung angefochten"); gewonnen: Sperre aufgehoben; verloren: wie Vollerstattung. Bestehende Sperren werden nie ueberschrieben
- Activity-Events `order:refunded` und `order:disputed` (auch im Webhook-Katalog), Mail an den Kunden bei Vollerstattung, Admin-Alert (M58). API: `refunded_at` und `disputed` in den Bestellungen. Migration `s9n0o1p2q3r4` (zwei Spalten, Up/Down geprueft). `backend/test_m59.py` (38 Tests). Im Stripe-Dashboard die drei Ereignisse zum Webhook hinzufuegen

### Added (M58 – Aktive Admin-Benachrichtigung)
- Neue Kanaele `ADMIN_ALERT_EMAIL` (kommagetrennt) und `ADMIN_ALERT_WEBHOOK_URL` (JSON-POST mit `content`, `text`, `subject`; Discord/Slack-kompatibel), beide leer = aus. Ausloeser: Billing-Tick ausgefallen (`billing_tick`), Fehler im letzten Tick (`billing_errors`), bezahlte Bestellungen warten zu lange (`waiting_orders`, M56) und Zahlungsereignisse mit Status `mismatch`/`unapplied` (je Bestellung und Status einmal)
- Entprellen ueber `system_state` (Schluessel `alert:<ausloeser>`): Meldung beim Wechsel gesund -> gestoert, danach hoechstens alle `ADMIN_ALERT_COOLDOWN_MINUTES` (Standard 360); einmalige Entwarnung (`ADMIN_ALERT_RECOVERY`). Versand best effort, stoert weder Tick noch Webhook; Webhook-URL wird nie geloggt
- Der Billing-Tick prueft vor und nach dem Lauf; neuer Compose-Service `alerts` ruft `python cli.py alert-check` unabhaengig davon alle `ALERT_CHECK_INTERVAL` Sekunden auf (erkennt auch einen toten Tick-Container). `python cli.py alert-test` schickt eine Testnachricht (Exit 1 ohne Kanal oder bei Fehler). `backend/test_m58.py` (26 Tests)

### Security (M57 – Tokens nach Passwortwechsel ungueltig)
- Access-Tokens enthalten den Claim `pwf` (Fingerabdruck des Passwort-Hashes). Nach Passwortwechsel oder -reset sind alle bisherigen Tokens des Kontos sofort ungueltig (401). `POST /api/auth/change-password` liefert zusaetzlich ein frisches `access_token`, das Frontend (`api.changePassword`) uebernimmt es, damit das aendernde Geraet angemeldet bleibt. Tokens ohne den Claim (vor diesem Update ausgestellt) gelten bis zu ihrem Ablauf. API-Keys sind nicht betroffen. `backend/test_m57.py` (11 Tests)

### Added (M56 – Warnung bei lange wartenden Bestellungen)
- `GET /api/admin/billing/status` enthaelt `awaiting_provisioning`: `count`, `oldest_paid_at`, `oldest_wait_hours`, `warn_after_hours`, `waiting_too_long`. Preflight-Check `billing_waiting_orders` warnt, wenn die aelteste bezahlte Bestellung ohne Instance `BILLING_WAIT_WARN_HOURS` (Standard 24) oder laenger wartet. Nur Warnung, nichts blockiert; Env-Variable in `.env.prod.example` und Compose. `backend/test_m56.py`

### Added (M55 – Job-Cleanup)
- `python cli.py cleanup-jobs [--days 30] [--dry-run]` loescht beendete Job-Eintraege (`completed`, `failed`), die vor mehr als N Tagen endeten; wartende, laufende und wiederholte Jobs bleiben immer. `--days` unter 1 ergibt Exit 2. Funktion `cleanup_jobs` in `app/infrastructure/jobs/cleanup.py`, `backend/test_m55.py` (10 Tests)

### Added (M54 – Bestaetigungsmails bei Zahlung)
- Zahlungseingang loest Mails aus: erste Zahlung mit Platz "Dein Server ist bereit" (mit Verbindungsadresse), ohne Platz "Zahlung eingegangen" mit Hinweis auf die automatische Bereitstellung, Verlaengerung "Zahlung eingegangen, Server verlaengert" mit neuem Laufzeitende. Keine Mails bei Wiederholung derselben Zahlungsreferenz und bei kostenlosen Paketen; Mailfehler brechen die Zahlung nicht ab
- `backend/test_m54.py` (11 Tests); `test_m46.py` zaehlt Zahlungsmails nicht mehr als Erinnerungen; Doku in `docs/orders-api.md`, `docs/known-limitations.md`

### Added (M53 – Ueberwachung des Billing-Ticks)
- Jeder Tick-Lauf (auch mit Fehlern) vermerkt Zeitpunkt und Ergebnis in der neuen Tabelle `system_state` (Schluessel `billing_tick`, Migration `r8m9n0o1p2q3`, Up/Down geprueft; neues Modell `SystemState`, ein kleiner Schluessel-Wert-Speicher fuer Betriebszustand)
- `GET /api/admin/billing/status`: `healthy`, `last_run_at`, `age_seconds`, `max_age_minutes`, `orders_needing_tick`, `orders_by_status`, `last_summary`. `healthy` ist false, wenn Bestellungen den Tick brauchen (active, past_due, awaiting_provisioning) und der letzte Lauf aelter als `BILLING_TICK_MAX_AGE_MINUTES` (Standard 15) ist oder fehlt
- Preflight-Check `billing_tick` (`ok`, `not_needed`, `warning` mit Alter und Zahl der wartenden Bestellungen); nur eine Warnung, blockiert nichts. Das Vermerken ist best effort und kann den Tick nie stoeren
- `backend/test_m53.py` (30 Tests, inkl. CLI-Lauf und Gegenprobe ohne Vermerken); Doku in `docs/orders-api.md`, `docs/known-limitations.md`, `docs/operations.md`

### Added (Betrieb: Tick-Ueberwachung durchgereicht)
- `BILLING_TICK_MAX_AGE_MINUTES` in `.env.prod.example` und `docker-compose.prod.yml`; `scripts/smoke-test.sh` prueft `GET /api/admin/billing/status` (`healthy`); Runbook Abschnitt 9/9a beschreibt Status-Endpunkt und externen Monitor

### Added (Admin: Zahlungsereignisse ansehen)
- `GET /api/admin/payment-events` (nur lesen, Admin-Guard): Zahlungsereignisse des Anbieters, neueste zuerst; Filter `status` (`processed`, `ignored`, `unapplied`, `mismatch`, `received`), `order_uuid`, `limit` (1 bis 500, Standard 100; ungueltige Werte ergeben 400). Damit lassen sich `mismatch` (Betrag/Waehrung weicht ab) und `unapplied` (Zahlung fuer beendete Bestellung, Erstattung pruefen) ohne Datenbankzugriff finden. Tests in `test_m48.py` (83), Doku in `docs/orders-api.md`

### Added (M52 – Automatische Bereitstellung wartender Bestellungen)
- Der Billing-Tick stellt bezahlte Bestellungen ohne Instance (`awaiting_provisioning`) automatisch bereit, sobald ein Node Platz hat (aelteste Zahlung zuerst; eine zu grosse Bestellung blockiert kleinere nicht). Erfolgreiche Bereitstellung: Status `active`, Event `order:provisioned`, Mail "Astra: Dein Server ist bereit" mit Verbindungsadresse; erfolglose Versuche sind still (kein Event und keine Mail pro Tick). Tick-Zusammenfassung enthaelt `provisioned`, `checked` zaehlt wartende Bestellungen mit
- **Die Laufzeit beginnt mit der Bereitstellung statt mit der Zahlung** (`fulfill_order(now=...)`): wer auf einen freien Node warten muss, verliert keine Zeit. Zahlungsreferenz und `paid_at` bleiben unveraendert, die Zahlung wird nie doppelt verbucht; die manuelle Bereitstellung per `mark-paid` funktioniert weiter. Gilt auch fuer Stripe-Zahlungen ohne Platz
- `backend/test_m52.py` (36 Tests: kein Spam, Reihenfolge, Teilkapazitaet, Fehlerisolation, Admin und Stripe, Gegenprobe ohne Wiederholung schlaegt fehl); Doku in `docs/orders-api.md` und `docs/known-limitations.md`

### Changed (M51 – Stub-Runner und Monitoring-Lebenszeichen)
- Der **Stub-Runner schliesst die Installation synchron ab**: `create_instance` liefert `data={"completed": True}`, der Service ruft dann den Install-Callback selbst auf (Status ready, `installed_at`, Event `instance:install_completed`). Gilt fuer Erstellung, Reinstall und Transfer (`instance.transfer.completed`). Vorher blieben Instanzen ohne Wings dauerhaft auf `provisioning`, seit M40 die Simulations-Knoepfe weg sind. Nur genau `completed is True` zaehlt; ein Fehler gewinnt immer; der **Wings-Adapter entfernt `completed`** aus Antworten, dort bleibt es beim asynchronen Callback ueber `/api/remote`
- Monitoring: Ein erfolgreicher Erreichbarkeits-Check (`daemon_reachable = true`) gilt als Lebenszeichen und setzt `last_seen_at` (hoechstens einmal pro Minute, nur aktive Agents). Dadurch widersprechen sich `daemon_reachable = true` und Health `unreachable` nicht mehr; Liste, Detail und Fleet-Summary zaehlen gleich. Mit dem Stub sind Agents im Monitoring sofort `healthy`
- **Aenderung fuer Tests/Entwicklung:** Instanzen sind nach Stub-Erstellung sofort ready (ein spaeterer Install-Callback ist idempotent). Tests, die den Zwischenzustand `provisioning`/`reinstalling` pruefen, nutzen einen asynchronen Runner (`test_m16`); Health-Klassifikationstests nutzen nicht erreichbare Daemons (`test_m22`)
- `backend/test_m51.py` (31 Tests), `test_m41.py` (42, Abschnitt "Lebenszeichen"); Doku in `docs/fleet-monitoring.md` und `docs/operations.md`

### Changed (M50 – Umlaute in Kundenmeldungen)
- Meldungen, die Kunden sehen (Auth, Client, Billing und die Services dahinter, inklusive Mails), tragen jetzt echte Umlaute: "Ungültige Anmeldedaten", "Instance gelöscht", "Bitte bezahle per Überweisung", Mailbetreffe wie "Astra: Zahlung überfällig – dein Server wurde gesperrt" (79 Texte in 12 Dateien). **Keine Änderung an Fehlercodes (`code`), Statuswerten oder Ereignisnamen.** Admin-Routen sowie Docstrings, Kommentare und Log-Ausgaben bleiben unverändert
- Neues Werkzeug `backend/tools/umlauts.py` mit festem Wörterbuch ganzer Wörter (Wörter wie "neue", "zuerst", "aktuell", "Blueprint", "queue" bleiben unberührt): `python tools/umlauts.py` zeigt noch vorhandene ASCII-Schreibweisen, `--write` korrigiert sie. Es arbeitet über den Syntaxbaum und fasst nur Meldungstexte an
- Die clientseitige Korrektur im Frontend (`lib/umlauts.ts`) wird dadurch für diese Meldungen zum No-op und kann bleiben
- Mails mit Umlauten werden per SMTP korrekt als UTF-8 kodiert (Betreff und Text, geprüft)
- `backend/test_m50.py` (34 Tests): Werkzeug, 19 echte API-Antworten und Mails ohne ASCII-Umlautersatz, Prüfung aller Kundendateien auf Wörterbuchtreffer, SMTP-Kodierung; schlägt bei einer zurückgedrehten Meldung fehl. `test_m46.py` und `test_m48.py` an die neuen Schreibweisen angepasst

### Docs (Phase-4-Abschluss)
- `docs/orders-api.md`: Meilenstein-Uebersicht, Abschnitte "Webhook-Signatur" (Header, HMAC-Schema, Proxy-Hinweis, Secret-Rotation, Selbsttest) und "Fehlersuche (Stripe)", Endpunkttabelle aktualisiert
- `docs/phase4-plan.md`: Umsetzungsstand je Schritt (M42 bis M49), Ausgangslage mit Status, Abweichungen vom Datenmodell, offene Punkte vor einem Betrieb mit Geld
- `docs/known-limitations.md`: neuer Abschnitt "Abrechnung und Shop" (keine Rechnungen/USt, keine automatischen Erstattungen, keine Mehrwaehrung, keine Abonnements, Stripe nur gemockt getestet, keine automatische Wiederholung der Bereitstellung, Bestell-Mails, Kapazitaet nach Zuweisung, kein CAPTCHA, Tick-Betrieb); korrigiert: der Admin-Transfer loescht auf dem alten Node und legt neu an, **Dateien werden nicht uebertragen**; JWTs bleiben nach Passwortwechsel gueltig

### Changed (M49 – Zeitstempel einheitlich UTC)
- Alle Zeitstempel in API-Antworten haben jetzt einen Zeitzonen-Suffix (`2026-10-03T12:00:00+00:00`). Bisher lieferten naive DB-Werte (SQLite/PostgreSQL) Strings ohne Suffix, die Browser als Ortszeit lesen. Neuer Helfer `iso_utc()` in `backend/app/utils/timeutil.py` (naiv gilt als UTC, aware wird nach UTC umgerechnet, `None` bleibt `None`), eingesetzt in allen `to_dict()`-Methoden (64 Stellen in 18 Dateien) und in den Bestell-Ereignisdaten
- **Aenderung fuer Clients:** die Werte aendern sich nur um den Suffix, nicht in der Zeit selbst. Die Idempotenz-Referenz `free-auto:<ende>` bleibt unveraendert
- `backend/test_m49.py` (23 Tests): Helfer, Stichprobe je Modell und ein Crawler, der alle GET-Routen aufruft und jeden zeitstempelartigen String auf Suffix prueft (47 Routen, 83 Zeitstempel); schlaegt ohne die Aenderung fehl

### Changed (M48 Vertrag – Checkout-Fehlercodes)
- `POST /api/client/orders/{uuid}/checkout`: Fehler tragen einen stabilen `code` (`manual`, `invalid_status`, `nothing_to_pay`, `unsupported_currency`, `provider_unavailable`, `provider_error`); `checkout_url` wird nur ausgeliefert, wenn sie mit `https://` beginnt (sonst 502). `test_m48.py` (64)

### Added (M48 – Zahlungsanbieter Stripe)
- `backend/app/domain/billing/payments.py`: Provider-Schnittstelle (`create_checkout`, `handle_webhook`) mit `ManualProvider` (Standard) und `StripeProvider` (Stripe Checkout `mode=payment`, Webhook mit `Webhook.construct_event`); `PAYMENT_PROVIDER=manual|stripe`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (`stripe==16.0.0` in `requirements.txt`)
- `POST /api/client/orders/{uuid}/checkout` -> `{checkout_url}` (pending_payment, active, past_due; 409 bei manual, anderem Status, Gratis-Bestellung und Waehrungen ohne Nachkommastellen; 502 bei Stripe-Fehler ohne Interna), `GET /api/client/billing-info` (oeffentlich)
- `POST /api/payments/stripe` (ohne Login, Signaturpruefung, Replay-Schutz): `checkout.session.completed`/`async_payment_succeeded` mit `payment_status=paid` verbuchen wie `mark-paid` (Referenz = PaymentIntent); Idempotenz ueber `payment_events` (Event-ID) und `payment_references`; Betrag/Waehrung-Abweichung -> `mismatch` ohne Freischaltung; Zahlung fuer stornierte/beendete Bestellung -> `unapplied`; beides mit Activity-/Webhook-Event `order:payment_unapplied`; kein Platz -> 200 und `awaiting_provisioning`; interne Fehler -> 500 (Stripe wiederholt)
- Neue Tabelle `payment_events` (Migration `q7l8m9n0o1p2`, Up/Down geprueft); Produktion meldet KRITISCH bei `PAYMENT_PROVIDER=stripe` ohne Schluessel oder unbekanntem Anbieter
- Gekuendigte Bestellungen bekommen vor Laufzeitende einmalig den Hinweis "Server wird am X geloescht" (Event `order:reminder`, `kind: deletion_notice`), normale Erinnerungen `kind: expiry_reminder`
- Doku: `docs/orders-api.md` (Einrichtung, Webhook-Regeln, Test-Modus); Tests: `backend/test_m48.py` (60, ohne Netzwerk: Checkout gemockt, Signaturen nach Stripes Verfahren), `test_m46.py` (86)

### Added (M46 Nachtrag – Erinnerung, Gratis-Verlaengerung, blueprint_name)
- Erinnerungsmail `BILLING_REMINDER_DAYS` (Standard 3, 0 = aus) vor Laufzeitende, Event `order:reminder`, hoechstens einmal pro Bestellung und Laufzeit (`orders.reminded_for_period_end`, Migration `p6k7l8m9n0o1`); nur bezahlte Bestellungen ohne Kuendigung mit Laufzeit laenger als das Fenster
- Kostenlose Bestellungen (`price_cents = 0`) werden vom Tick bei Ablauf automatisch verlaengert statt gesperrt und geloescht (der Kunde kann nichts bezahlen); gekuendigte laufen zum Laufzeitende aus. Tick-Zusammenfassung enthaelt jetzt `reminded` und `renewed`
- `Product.to_public_dict()`/`to_dict()` liefern `blueprint_name` (Listen laden den Blueprint per Join mit), `blueprint_id` bleibt intern
- Tests: `test_m46.py` (83), `test_m44.py` (87)

### Added (M46 – Billing-Tick)
- `python cli.py billing-tick` (idempotent, alle paar Minuten per Cron/Compose): `active` + Laufzeit abgelaufen -> `past_due` (Instance suspendiert mit Grund "Zahlung überfällig", synchronisiert und auf dem Node beendet, Mail); `past_due` laenger als `BILLING_GRACE_DAYS` (Standard 7) -> Instance geloescht (`force`), `expired`, Mail; Kuendigung zum Laufzeitende -> sofort geloescht; fehlende Instance -> `expired` ohne Runner-Aufruf. Ausgabe als JSON `{checked, past_due, expired, errors}`, Exit-Code 1 bei Fehlern
- Karenzzeit zaehlt ab `orders.past_due_at` (nicht ab Laufzeitende), ein Tick-Ausfall kostet Kunden keine Karenzzeit; bestehende Admin-Sperren werden nicht ueberschrieben; bei laufender Installation/Transfer wartet der Tick bis zu einen Tag; jede Bestellung wird einzeln committed, Fehler blockieren die anderen
- Verlaengerung ueber `POST /api/admin/orders/{uuid}/mark-paid` auf `active`/`past_due`: neues Ende ab `max(jetzt, altes Ende)`, `payment_reference` ist **Pflicht** (400) und macht den Aufruf idempotent (verbuchte Referenzen in `orders.payment_references`), hebt nur die Sperre "Zahlung überfällig" auf. **Aenderung gegenueber M44:** mark-paid auf eine aktive Bestellung ist ohne Referenz kein No-op mehr, sondern 400
- `delete_instance` loest verknuepfte Bestellungen von der Instance (Fremdschluessel `orders.instance_id`; ohne das scheitert das Loeschen einer bestellten Instance auf PostgreSQL) und setzt lebende Bestellungen auf `expired`
- Bestellungen liefern `past_due_at` und `scheduled_deletion_at`; neue Events `order:past_due`, `order:renewed`, `order:expired`; Config `BILLING_GRACE_DAYS`
- Migration `o5j6k7l8m9n0` (`orders.past_due_at`, `orders.payment_references` mit Backfill aus `payment_reference`), Datum/Zeit der Bestellungen jetzt durchgehend naive UTC
- `suspend_instance`/`unsuspend_instance` akzeptieren `admin_user_id=None` (System) ohne Logging-Fehler
- `backend/test_m46.py` (65 Tests, Zeit per `now=` eingefroren), `docs/orders-api.md` ergaenzt

### Added (M44 – Produkte und Bestellungen)
- Neue Tabellen `products` und `orders` (Migration `n4i5j6k7l8m9`, Upgrade/Downgrade geprueft, Schema stimmt mit `create_all` ueberein). Bestellungen halten einen Schnappschuss von Preis, Laufzeit und Ressourcen
- Admin: `GET/POST /api/admin/products`, `GET/PATCH/DELETE /api/admin/products/{id}`, `GET /api/admin/orders` (Filter `status`, `user_id`), `GET /api/admin/orders/{uuid}`, `POST /api/admin/orders/{uuid}/mark-paid` (manuelle Zahlung, stellt die Instance per automatischer Platzierung bereit; idempotent; ohne freien Node bleibt die Bestellung `awaiting_provisioning` und kann erneut bereitgestellt werden)
- Kunde: `GET /api/client/products` (oeffentlich, nur aktive Pakete ohne interne Felder), `POST /api/client/orders`, `GET /api/client/orders[/{uuid}]`, `POST /api/client/orders/{uuid}/cancel` (offen: sofort, aktiv: zum Laufzeitende)
- Regeln: max. 5 offene Bestellungen pro Kunde, `max_instances_per_user` je Paket, kostenlose Pakete nur mit Limit und sofort bereitgestellt, bestaetigte E-Mail wenn `EMAIL_VERIFICATION_REQUIRED`, Produkt mit Bestellungen und Blueprint mit Produkten nicht loeschbar (409)
- Neue Activity-/Webhook-Events `order:created`, `order:paid`, `order:provision_failed`, `order:cancelled`
- `docs/orders-api.md`, `backend/test_m44.py` (84 Tests)

### Added (M43 – Instance loeschen)
- `delete_instance(instance, actor_id, force)` im Instance-Service: Runner-Aufraeumen best effort (Backups, Datenbanken, Instance auf dem Node; Fehler werden geloggt und als `runner_cleanup: "failed"` gemeldet, das Panel loescht trotzdem), Endpoints werden freigegeben (Zeilen bleiben), Backups/Datenbanken/Collaborators/Routines inkl. Actions werden entfernt, Activity-Eintraege bleiben erhalten
- Laufende Vorgaenge (`provisioning`, `reinstalling`, `restoring`, `transferring`) -> 409, ausser Admin mit `force: true`
- `DELETE /api/admin/instances/{uuid}` (Admin-Guard, optional `{"force": true}`) und `DELETE /api/client/instances/{uuid}` (nur Owner, Body `{"confirm": "<Name>"}` case-sensitiv, suspendierte Instances -> 409, Collaborators und Fremde -> 404, `force` fuer Owner nicht moeglich)
- Neues Activity-/Webhook-Event `instance:deleted` (mit Name, UUID, Owner, Agent, `runner_cleanup`, `forced`)
- `backend/test_m43.py` (40 Tests)

### Added (M42 – Kapazitaetspruefung und Platzierung)
- `backend/app/domain/agents/placement.py`: `capacity_problem()`, `used_resources()` und `pick_agent(memory, disk, cpu)` (aktiv, nicht in Wartung, freier Endpoint, genug freie effektive Kapazitaet inkl. Overalloc; Auswahl nach geringster Auslastung nach der Platzierung, Gleichstand: weniger Instanzen, kleinere ID)
- `create_instance` bricht mit 409 ab, wenn RAM, Disk oder CPU des gewaehlten Agents nicht reichen (Meldung nennt Dimension und freien Rest); Agents mit `*_total = 0` gelten je Dimension als ohne Limit. Zeilensperre auf dem Agent serialisiert parallele Erstellungen auf PostgreSQL
- `POST /api/admin/instances`: `agent_id` ist optional, fehlt es oder ist `null`, platziert Astra automatisch (409 ohne passenden Agent, `endpoint_id` ohne `agent_id` -> 400)
- Transfer prueft die Kapazitaet des Ziel-Agents (409)
- `backend/test_m42.py` (23 Tests)

### Added (Account und SFTP-Port)
- `POST /api/auth/change-password` – `{current_password, new_password}` fuer eingeloggte Nutzer; 401 bei falschem aktuellem Passwort (und ohne Login), gleiche Regeln wie bei der Registrierung (mind. 8 Zeichen), neues Passwort muss sich unterscheiden, Activity-Events `auth:password_changed` / `auth:password_change_failed`, offene Reset-Links werden ungueltig, Rate Limiting aktiv. Bereits ausgestellte JWTs bleiben bis zum Ablauf gueltig
- `instance.connection` enthaelt jetzt `sftp_port` (Port des Agents), damit auch Nicht-Admins die SFTP-Zugangsdaten anzeigen koennen
- Tests in `test_m34.py` (30) und `test_m39.py` (29)

### Added (M41 – Wings-Erreichbarkeit und Endpoint-Pflicht)
- Fleet Monitoring (`GET /api/admin/agents/monitoring`, `/agents/{id}/monitoring`) liefert `daemon_reachable`, `daemon_version` und `daemon_error`, ermittelt per `GET /api/system` am Wings (Bearer `daemon_token`, Timeout 3 s, Ergebnis 30 s gecacht, Cache-Schluessel enthaelt URL und Token; mehrere Agents werden parallel geprueft). Mit dem Stub-Adapter immer `true`/`"stub"` (`backend/app/domain/agents/reachability.py`)
- Preflight: neuer Check `agents_reachable`, warnt bei nicht erreichbaren aktiven Agents (Agents in Wartung und inaktive Agents werden nicht geprueft), blockiert nicht
- Kein stiller Standard-Port mehr: Hat eine Instanz keinen primaeren Endpoint, setzt der Config-Builder `SERVER_PORT` und `allocations.default.port` auf `0` (wie `allocation->port ?? 0` im Referenz-Panel), `allocations.mappings` bleibt leer und es gibt eine Log-Warnung (vorher 25565)
- Bestaetigt und getestet: `create_instance` bricht ohne freien (oder nur gesperrten) Endpoint mit 409 ab und speichert nichts
- `backend/test_m41.py` (27 Tests)

### Fixed / Added (E-Mail-Links und Verifizierungs-Frontend)
- Fix: Der Link in der Passwort-Reset-Mail zeigte auf `/reset-password`, die Frontend-Route heisst `/password-reset/confirm` (Link fuehrte auf die 404-Seite); Tests pruefen jetzt beide Mail-Links gegen die Frontend-Routen
- `POST /api/auth/resend-verification` akzeptiert zusaetzlich `login` (Benutzername oder Adresse), Antwort bleibt neutral
- Frontend: neue Seite `/verify-email` (Ziel des Mail-Links), Registrierung zeigt bei aktiver Verifizierung den Hinweis "E-Mail bestaetigen" mit "Erneut senden", Login zeigt bei `email_not_verified` einen Hinweis mit Knopf zum erneuten Senden; `ApiError` traegt HTTP-Status und Fehlercode

### Removed (M40 – Legacy /api/agent)
- Der Blueprint `/api/agent` (`instances/{uuid}/install`, `instances/{uuid}/container/status`, `sftp-auth`, `health`) wurde komplett entfernt. Wings und alle Agents nutzen `/api/remote` mit Node-Token. Der Agent-Guard aus M36 samt `AGENT_GUARD_ENABLED` und `test_m36.py` entfaellt damit
- Frontend: Dev-Knopf "Simuliere Install-Callback" und `api.reportInstallResult` entfernt (er lief seit M36 in einen 403)
- Tests M15–M20, M27, M30, M33 nutzen jetzt die Remote-API ueber `backend/test_helpers.py` (`report_container_state`, `report_install`, `node_headers`); der Fingerprint-Pfad der Legacy-Route ist weiter ueber `authorize_ssh_key_access()` abgedeckt (M30 b)
- `backend/test_m40.py` (11 Tests) stellt sicher, dass `/api/agent/*` 404 liefert und `/api/remote` Token verlangt

### Security (M36 – Agent-Guard, durch M40 abgeloest)
- `/api/agent/*` verlangt jetzt den Node-Token (`Authorization: Bearer {token_id}.{token}`, gleiche Pruefung wie `/api/remote`). Ausnahme: `GET /api/agent/health`
- Ein Agent darf nur Instanzen seines eigenen Nodes melden (`install`, `container/status` -> 403, `sftp-auth` -> `allowed: false, reason: instance_not_on_node`)
- Schalter `AGENT_GUARD_ENABLED` (Standard `true`), nur in `TestingConfig` aus
- `backend/test_m36.py` (17 Tests)

### Added (M39 – Endpoint-Bulk und Verbindungsadresse)
- `POST /api/admin/agents/{id}/endpoints/bulk` – Body `{ip, port_start, port_end}` legt einen Port-Bereich an, ueberspringt vorhandene (`ip` + `port` je Agent). Antwort `{created, skipped, endpoints}` (nur neu angelegte), 201 bei neuen Endpoints, sonst 200. Grenzen: 1..65535, `port_start <= port_end`, max. 1000 Ports pro Aufruf, `ip` muss gueltig sein
- `Instance.to_dict()` liefert `connection`: `{host, ip, port, address}` (`host` = FQDN des Agents, `address` = `host:port`), `null` ohne primaeren Endpoint. Admin- und Client-Listen laden Agent und Endpoint per Join mit, keine Query pro Instanz
- `backend/test_m39.py` (27 Tests)

### Added (M38 – E-Mail-Verifizierung)
- `EMAIL_VERIFICATION_REQUIRED` (Standard `false`): Registrierung sendet einen Bestaetigungs-Link (`EMAIL_VERIFICATION_TTL_HOURS`, Standard 48), Login ist erst nach Bestaetigung moeglich (403, `code: email_not_verified`)
- `POST /api/auth/verify-email` und `POST /api/auth/resend-verification` (antwortet immer gleich); Token ist an die Adresse gebunden
- Neue Spalte `users.email_verified_at` (Migration `m3h4i5j6k7l8`): bestehende Nutzer werden mit `created_at` als bestaetigt markiert, vom Admin angelegte Nutzer und der Bootstrap-Admin ebenfalls; ein erfolgreicher Passwort-Reset bestaetigt die Adresse
- `User.to_dict()` liefert `email_verified`
- `backend/test_m38.py` (22 Tests)

### Added (M37 – Egg-Import)
- `backend/app/domain/blueprints/egg_import.py`: `convert_egg()` wandelt Pterodactyl-Eggs (PTDL_v1/v2) und Pelican-Eggs (PLCN_v1..v3) in Blueprint-Felder um (JSON-String-Configs, `docker_images`, `startup_commands`, `env_variable` -> `env_var`, `^C` -> `^SIGINT`); Platzhalter bleiben unveraendert
- `POST /api/admin/blueprints/import` – Egg oder natives Blueprint-JSON (`"format": "astra"`) -> 201 mit Blueprint, 400 bei ungueltigen Daten
- CLI: `python cli.py import-blueprint <datei.json|yaml>`
- `blueprints/minecraft-paper.json` – reduziertes Beispiel-Egg (Paper, Java 21). Die Minecraft-EULA wird nicht automatisch akzeptiert
- `backend/test_m37.py` (35 Tests)

### Added (Self-Service Teil 1)
- `POST /api/auth/register` – Selbstregistrierung, standardmaessig AUS (`REGISTRATION_ENABLED=true` zum Aktivieren), neue Nutzer sind nie Admin
- `POST /api/auth/password-reset/request` und `/confirm` – Reset per signiertem, zeitlich begrenztem Einmal-Link (`PASSWORD_RESET_TTL_MINUTES`, Standard 60), antwortet unabhaengig von der Adresse gleich
- `backend/app/infrastructure/mail.py` – SMTP-Versand (`MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`), ohne `MAIL_SERVER` nur Logging
- `FRONTEND_URL` fuer den Link in der Reset-Mail
- Neue Auth-Pfade unterliegen dem Rate Limiting
- `backend/test_m34.py` (18 Tests)

### Changed
- Rate Limiting fuer `/api/auth/login` nutzt jetzt Redis (geteilter Zaehler ueber alle Gunicorn-Worker), mit In-Memory-Fallback wenn Redis nicht erreichbar ist (`backend/app/infrastructure/ratelimit.py`)
- `redis` zu `backend/requirements.txt` hinzugefuegt

### Added (Frontend)
- Meine Bestellungen aktualisiert sich alle 30 s still (nur bei sichtbarem Tab, abschaltbar, Einstellung wird gemerkt), damit der Wechsel von "wird bereitgestellt" auf "aktiv" ohne Neuladen sichtbar wird; Hinweistext zur automatischen Bereitstellung (M52)
- CI fuer das Frontend (`.github/workflows/frontend.yml`): Typecheck, Vitest und Build bei Aenderungen unter `frontend/`
- Meine Bestellungen auf schmalen Bildschirmen (<= 640 px) als Karten statt Tabelle (Aktionen waren sonst ausserhalb des sichtbaren Bereichs); Admin-Navigation bricht in mehrere Zeilen um statt abgeschnitten zu scrollen; `frontend/README.md` neu (Routen, Struktur, vom Betreiber zu pflegende Dateien, Hinweise); letzte ASCII-Umlaute in Admin-Formularen korrigiert
- Sicherer Instance-Transfer (Admin): statt des Ein-Klick-Transfers ein Dialog (`TransferInstanceForm`) mit roter Warnung "Beim Transfer werden die Serverdaten NICHT uebertragen …", Pflicht-Checkbox "Ich habe ein aktuelles Backup" und Bestaetigung per Instanzname; Backup-Pruefung ueber `GET /admin/instances/{uuid}/backups` (`successful_count`, `last_successful_backup_at`): ohne erfolgreiches Backup ist der Transfer gesperrt, sonst wird das letzte Backup mit Datum angezeigt; ist die Abfrage nicht moeglich, gilt nur die Checkbox
- Zahlungsweg ueber `GET /client/billing-info` (einmal beim Laden von `/orders`): bei manuellem Anbieter werden keine Bezahl-Buttons gerendert, sondern direkt der Hinweis aus `src/legal/payment.ts`; 409 "manual" bleibt Fallback. Kostenlose Bestellungen zeigen weder Bezahl-Button noch Ueberweisungshinweis
- Stripe-Frontend an den Vertrag angepasst: "Verlängern und bezahlen" bei aktiven/ueberfaelligen Bestellungen, Hinweis zum manuellen Zahlungsweg aus zentraler Konstante (`src/legal/payment.ts`), Toasts "Zahlung eingegangen, Server wird bereitgestellt." / "Zahlung abgebrochen.", Nachladen nach 5 s
- Alle Backend-Zeitstempel werden als UTC gelesen (`parseUtc`, `formatDateTime`, `formatTimeAgo`, ...): Aktivitaetslog, Backups, Routinen, API-Keys, SSH-Keys, Jobs, Agents, Blueprints, Fleet Monitoring. Behebt falsche "vor X Std."-Angaben in Browsern ausserhalb von UTC; Strings mit Zeitzonen-Suffix (z.B. `+00:00`) bleiben unveraendert
- Stripe-Vorbereitung auf `/orders`: Button "Jetzt bezahlen" fuer unbezahlte Bestellungen (`POST /client/orders/{uuid}/checkout` -> Weiterleitung zur `checkout_url`, nur https); bei 409 "manual" verschwindet der Button und es erscheint der Hinweis zur Zahlung per Ueberweisung; Rueckkehr `?paid=<uuid>` (Dank-Toast, Status wird bis zur Bestaetigung nachgeladen) und `?cancelled=<uuid>` (Hinweis, Bestellung bleibt offen)
- Billing-Tick-Vertrag (M46): Admin-Bestellungen mit "Verlaengern (Zahlung erfassen)" bei active/past_due (Zahlungsreferenz Pflicht), Warnhinweise bei Kunden und Admin (`OrderNotice`): "Gesperrt seit …" und "Server wird am … geloescht" (rot) bei past_due, "Laeuft bis …, wird dann geloescht" bei gekuendigten aktiven Bestellungen; Lösch-Dialog nennt bei laufender Bestellung "… eine Erstattung erfolgt nicht"; Zeitstempel ohne Zeitzone werden als UTC gelesen (`parseUtc`, `formatDateTime`); Vitest laeuft mit fester Zeitzone UTC
- Rechtsseiten `/impressum`, `/datenschutz`, `/agb` (ohne Login erreichbar, Platzhaltertexte mit Hinweis "vom Betreiber auszufuellen", Betreiberdaten zentral in `src/legal/operator.ts`, offene Platzhalter hervorgehoben), Footer mit Rechtslinks auf allen Seiten inkl. Login/Registrierung (`SiteFooter`); Registrierung mit Pflicht-Checkbox "Ich akzeptiere die AGB und die Datenschutzerklaerung"
- Admin-Dashboard: Karte "Offene Bestellungen" (pending_payment + awaiting_provisioning, Links auf `/admin/orders?status=...`; der Statusfilter der Bestellliste wird aus der URL uebernommen)
- Login und Registrierung kehren per `?redirect=` zur urspruenglichen Seite zurueck (nur interne Pfade, Schutz vor Open Redirect, `lib/redirect.ts`); geschuetzte Routen leiten mit Rueckkehrziel zum Login. `/shop` bleibt fuer den Pilot geschuetzt. Admin-Bestellungen heben `awaiting_provisioning` hervor; Blueprint-Name auf Shop-Karten, sobald das Backend ihn liefert
- Phase 4 gegen die echten Endpunkte (M44, `docs/orders-api.md`): Admin-Produkte `/admin/products` (CRUD, Euro<->Cent, Ressourcen flach im Body, `is_active`, Gratis-Produkte brauchen `max_instances_per_user`), Kunden-Shop `/shop` (Karten, Bestellung mit optionalem Servername, Hinweise je Status), Meine Bestellungen `/orders` (Bestellungen per `uuid`, Status-Badges inkl. `awaiting_provisioning`, Verbindungsadresse, Stornieren sofort vs. Kuendigen zum Laufzeitende), Admin-Bestellungen `/admin/orders` (Statusfilter, "Als bezahlt markieren" mit optionaler Zahlungsreferenz, "Erneut bereitstellen", 409-Text). Navigation "Shop"/"Meine Bestellungen" fuer alle, "Produkte"/"Bestellungen" fuer Admins; Dashboard verweist Kunden ohne Server auf den Shop
- Instance loeschen (M43): Owner auf der Detailseite ("Instance loeschen", `DELETE /client/instances/{uuid}` mit Namensbestaetigung; gesperrte Instances nur durch Admins), Admin in der Instance-Liste (`DELETE /admin/instances/{uuid}`, "Erzwingen" bei laufenden Vorgaengen, Hinweis wenn das Aufraeumen auf dem Node fehlschlug). Bestaetigung erst nach exakter Eingabe des Namens (`DeleteInstanceForm`); nach dem Loeschen als Owner Redirect aufs Dashboard mit Toast, Admins bekommen bei `runner_cleanup: failed` einen Warn-Toast ("Aufraeumen auf dem Node fehlgeschlagen, bitte Wings pruefen"), Kunden bei gesperrter Instance den Hinweis "Gesperrt, bitte Support kontaktieren"
- Agent-Formular (Erstellen/Bearbeiten): Kapazitaet Memory/Disk/CPU gesamt und Ueberallokation je Dimension (0 = kein Limit), Validierung 0..1000 % fuer Ueberallokation
- Instance-Erstellung mit automatischer Platzierung (M42): Agent-Auswahl "Automatisch (nach Kapazitaet)" als Standard (`agent_id: null`), Endpoint-Feld nur bei gewaehltem Agent, 409-Text der Platzierung wird angezeigt
- Kapazitaet je Agent auf der Agents-Seite: Memory/Disk/CPU "belegt von effektiv" mit Balken (gemeinsame Komponente `UtilizationBar`, "kein Limit" bei Gesamtwert 0, Progressbar-Semantik)
- Wings-Status (`DaemonStatus`) auf Fleet Monitoring und Agents-Seite: Badge "Wings erreichbar"/"nicht erreichbar" (Fehler als Tooltip) und Version aus `daemon_reachable`/`daemon_version`/`daemon_error`
- Konto-Seite `/account` (Navigation "Konto"): Profil, MFA/TOTP einrichten (QR-Code clientseitig mit `qrcode`, Secret als Text, Verifikation, Recovery-Codes einmalig) und deaktivieren, API-Keys (Liste, anlegen, loeschen; Token nur einmal sichtbar), Link auf SSH-Keys, "Passwort aendern" (`POST /auth/change-password`, mit Hinweis zu bestehenden Sitzungen)
- Login: zweiter Schritt fuer MFA (`requires_mfa` -> Code/Recovery-Code); vorher konnten sich MFA-Nutzer im Frontend nicht anmelden
- Agents-Seite: Health-Badge je Agent (`GET /admin/agents/monitoring`, 15s Auto-Refresh), optional "Wings erreichbar"/Version sobald `daemon_reachable`/`daemon_version` geliefert werden
- Kunden-/Admin-Trennung im UI: Admin-Links nur fuer `is_admin`, Admin-Routen leiten Kunden zum Dashboard um (`AdminRoute`, `useCurrentUser`); Dashboard zeigt den Benutzernamen statt "User #id" und einen Kunden-Leerzustand
- Instance-Detail: Box "SFTP-Zugang" (Host, Port, Benutzername `<user>.<uuid[:8]>` mit Kopier-Buttons, Hinweis auf Panel-Passwort/SSH-Key). Port aus `connection.sftp_port`, fuer Admins sonst aus der Agent-Liste
- Endpoint-Formular: Port-Bereich (`25565-25600`) ueber `POST /admin/agents/{id}/endpoints/bulk`, Ergebnis-Toast "n angelegt, m uebersprungen"; Einzelport wie bisher (`lib/portRange.ts`)
- Blueprint-Import-UI (`BlueprintImport`) auf der Blueprint-Admin-Seite: Egg-JSON per Datei oder Textarea, Vorschau, Aufruf `POST /api/admin/blueprints/import` (Feature-Flag entfernt, immer sichtbar)
- Verbindungsadresse (`ConnectionAddress`) mit Kopier-Button auf Dashboard und Instance-Detail; erscheint, sobald die Instance-Antwort ein Feld `connection` {host, port, address} liefert
- Agents: Bearbeiten-Formular (`PATCH /admin/agents/{id}`) und getrennte Felder Connect-Port (Panel -> Wings, z.B. 443 hinter Caddy) und Listen-Port (Wings lokal, z.B. 8080) im Erstellen- und Bearbeiten-Formular; Port-Validierung 1-65535
- Self-Service (M34-Frontend): `RegisterPage` (/register), `ForgotPasswordPage` (/password-reset), `ResetPasswordPage` (/password-reset/confirm?token=), Links auf der LoginPage; Meldung "Registrierung ist deaktiviert"; clientseitige Validierung (Passwort min. 8 Zeichen)
- `PageLayout`: SPA-Navigation per `react-router` (kein Seiten-Reload), `aria-current`, Abmelden-Button
- `FileBrowser`: Upload von Textdateien (max. 1 MB, Workaround ueber Write-Endpoint) und "Neue Datei"
- Auto-Refresh (15s, abschaltbar, nur bei sichtbarem Tab) fuer Jobs-Dashboard, Fleet Monitoring, Dashboard und Admin-Instances (`hooks/useAutoRefresh.ts`, `AutoRefreshToggle`)
- 401-Handling: abgelaufene Sitzung leitet zu `/login?expired=1` mit Hinweis um
- `ErrorBoundary` gegen weisse Seite bei Render-Fehlern, `NotFoundPage` als Catch-all-Route
- Mobile-Navigation (<=760px): Hamburger-Menue mit gruppierten Links und Abmelden, schliesst bei Seitenwechsel/Escape (`hooks/useMediaQuery.ts`); Login leitet eingeloggte Nutzer zum Dashboard
- `LoginPage`: gemeinsame UI-Styles, Label-Verknuepfung, `autocomplete`, `role="alert"`

### Changed (Frontend)
- Ende-zu-Ende gegen das echte Backend geprueft (Registrierung, Passwort aendern ohne Ausloggen bei falschem Passwort, MFA mit echtem TOTP-Code, API-Keys, Bestellung/Zahlung/Verlaengerung/Kuendigung, Server loeschen, Produkte, Agents mit Kapazitaet, automatische Platzierung). Dabei behoben: unbeschriftete Checkboxen in der Dateiliste, englischer Rohstatus im Loesch-Hinweis (deutsches Label), deutsche Health-Labels, "Kapazitaet" in Backend-Fehlertexten
- Kunden-Durchsicht (verstaendliche Texte): korrekte Umlaute in allen Kundentexten; ASCII-Schreibweisen aus Backend-Meldungen werden korrigiert (`lib/umlauts.ts`, z.B. "Ungültige Anmeldedaten"); technische Statuscodes ("Request failed: 500") durch allgemeine Meldungen ersetzt; Fehlerseite ohne technischen Text (Details einklappbar); "Instance" heisst fuer Kunden "Server"; Steuerung auf der Server-Seite mit deutschen Beschriftungen (Starten, Stoppen, Neustarten, "Beenden erzwingen" mit Rueckfrage, "Neu installieren"); deutsche Statuslabels (bereit, laeuft, gestoppt, wird eingerichtet, gesperrt ...); Konsole und Fehlerfallbacks ohne Fachbegriffe (Token, WebSocket, Daemon)
- Barrierefreiheit: Link-Farbe `#1565c0`, Kontrast im Sperr-Banner und in der Konsole, Beschriftung der Benutzerauswahl bei Mitbenutzern (axe auf Dashboard, Server-Seite, Konto, Bestellungen, Shop sauber)
- API-Client: 401 von `/auth/change-password` (falsches aktuelles Passwort) loggt nicht mehr aus
- Verstaendliche Fehlermeldungen im API-Client: 403 vom Admin-Guard -> "Nur Administratoren duerfen diese Aktion ausfuehren.", nicht erreichbarer Server -> eigene Meldung (`lib/errors.ts`)
- Kunden-Dashboard: Platzhalter "Noch kein Server. Bestellung folgt in Phase 4." (Admins weiter mit Hinweis auf den Admin-Bereich), Komponententests fuer Leer-/Fehler-/Normalzustand
- Frontend-Tests mit Vitest (`npm test`, 54 Tests): Login/Registrierung/Passwort-Reset inkl. E-Mail-Verifizierung (Komponententests), SFTP-Box, Port-Bereich, Egg-Parser, Agent-Formular-Validierung, `useAutoRefresh`, API-Client (Bearer-Token, 401-Handling, Reset-Payload); Logik dafuer nach `src/lib/` ausgelagert
- Barrierefreiheit (axe-core, WCAG 2 A/AA, 13 Seiten ohne Verstoesse): Kontraste bei Grautexten, Status-Badges und Kennzahlen, Labels fuer Selects/Inputs auf Agents-, Instances-, Jobs- und Monitoring-Seite
- Responsive Layout: dynamisches Padding, horizontal scrollbare Tabellen, `FileBrowser`-Grid bricht auf schmalen Screens um

## [0.33.0-rc] - 2026-10-03

### Added (M33 – Wings Remote-API)
- `backend/app/api/remote/` – Remote-API unter `/api/remote`, die ein unveraenderter Wings-Daemon
  (Pterodactyl/Pelican) am Panel aufruft. Pfade und Formate wie `routes/api-remote.php` im Referenz-Panel:
  - `GET /servers` (paginiert, Wings-Boot), `POST /servers/reset`
  - `GET /servers/{uuid}` (settings + process_configuration), `GET/POST /servers/{uuid}/install`
  - `POST /servers/{uuid}/container/status`, `GET|POST /servers/{uuid}/transfer/success|failure`
  - `POST /sftp/auth` (Passwort und Public Key, Wings-Permission-Mapping)
  - `POST /activity` (Wings-Events werden als ActivityLog mit subject_type=instance gespeichert)
  - `GET|POST /backups/{uuid}`, `POST /backups/{uuid}/restore`
- Node-Token-Authentifizierung (`Authorization: Bearer {token_id}.{token}`), konstante Zeitvergleiche,
  jeder Request aktualisiert `last_seen_at` des Agents
- Agent-Credentials werden beim Anlegen automatisch erzeugt; `POST /api/admin/agents/{id}/rotate-credentials`
- `GET /api/admin/agents/{id}/configuration` – Wings `config.yml` (YAML + JSON) pro Agent
- `PATCH /api/admin/agents/{id}` – Wings-Verbindungsfelder pflegen (scheme, behind_proxy, Ports, daemon_base, upload_size)
- Agent-Felder: `uuid`, `behind_proxy`, `daemon_sftp`, `daemon_base`, `upload_size`
- Blueprint-Felder fuer die Wings-Prozesskonfiguration: `install_container`, `install_entrypoint`,
  `config_startup`, `config_stop`, `config_files`, `file_denylist`
- `config_builder.py`: `egg`-Block in den settings, `build_process_configuration()`,
  `build_install_payload()`, Platzhalter-Ersetzung (`{{server.*}}`, `{{env.*}}`) fuer Config-Dateien
- Frontend: Agents-Seite zeigt Token-ID, config.yml-Dialog und Credential-Rotation; Blueprint-Formular
  mit Install-Container, Stop-Befehl, Startup-Erkennung und Datei-Denylist
- Migration `l2g3h4i5j6k7_milestone33_wings_remote_api`
- `docs/wings-remote-api.md` – Endpunkte, Auth, Node-Einrichtung, Fehlersuche
- Testsuite `backend/test_m33.py`

### Changed
- Backups/Restore: Wings antwortet asynchron (202). Ein Backup gilt erst nach dem Remote-Callback als
  erfolgreich; der Stub meldet weiterhin synchron (`completed: true`)
- Websocket-Token enthaelt `user_uuid` (User-ID als String) fuer Wings-Activity-Events; `iss` faellt auf `BASE_URL` zurueck
- `backend/app/version.py`: VERSION auf `0.33.0-rc`
- `requirements.txt`: PyYAML fuer den config.yml-Export

### Fixed
- `backend/test_m30.py` rief `/agent/sftp-auth` statt `/api/agent/sftp-auth` auf (Testsuite brach ab)

### Notes
- M33 schliesst die groesste Luecke fuer den Pilotbetrieb: Ohne Remote-API konnte Wings keinen Server booten
- Bewusst nicht enthalten: S3-Presigned-Uploads, Mounts, Rate-Limit auf `/sftp/auth`


## [0.32.0-rc] - 2026-03-16

### Added (M32 – Pilotbetrieb & v1.0-Rollout)
- `docs/pilot-rollout-plan.md` – vollständiger Pilot-Rollout-Plan:
  - Pilotziel, Pilotumfang (was aktiv / was nicht)
  - Beteiligte Rollen (Pilot-Admin, Nutzer, Reviewer, Dev-Bereitschaft)
  - Pilotumgebung mit Infrastruktur-Diagramm und Mindest-Sizing
  - Go/No-Go-Checkliste vor Pilotstart (Infrastruktur, Backend, Agent, Readiness)
  - 12 verbindliche Pilot-Kernflows mit Akzeptanzkriterien
  - Pilot-Protokoll-Vorlage für Funde (Blocker/Major/Minor/Nice-to-have)
  - Feedback-Priorisierungsmatrix und Release-Konsequenzen
  - Rollback-Anleitung für den Pilot
  - Scope-Freeze-Definition (erlaubt / nicht erlaubt bis v1.0)
- `docs/release-plan.md` – Versions-Roadmap und Go-Live-Kriterien:
  - Versions-Roadmap: v0.32.0-rc → Pilot-Build → v1.0.0
  - Scope-Freeze: nur Bugfixes / Security Fixes / Ops-Fixes vor v1.0
  - Vollständige Go-Live-Kriterien (Pilot-Abschluss, Qualität, Upgrade/Recovery, Doku)
  - Rollback- und Recovery-Anleitung (fehlgeschlagenes Release, fehlgeschlagene Migration)
  - Release-Notes-Template für v1.0.0
  - SemVer-Strategie und Build-Metadaten
  - Post-v1.0-Roadmap (P1/P2-Features)

### Changed
- `backend/app/version.py`: VERSION aktualisiert auf `0.32.0-rc`, neues `RELEASE_PHASE`-Feld (`pilot`)
- `backend/app/__init__.py`: `/ops/info` Endpunkt gibt nun `release_phase` zurück
- `backend/app/version.py`: `get_version_info()` enthält `release_phase`
- `frontend/src/services/api.ts`: `SystemVersionInfo`-Interface um `release_phase` erweitert
- `frontend/src/pages/AdminSystemPage.tsx`: Release-Phase wird in der System-Info-Seite angezeigt

### Notes
- M32 ist primär ein Dokumentations- und Planungs-Meilenstein
- Minimale Code-Ergänzungen: Versionsanhebung und `release_phase`-Feld für operative Klarheit
- Scope ist ab jetzt eingefroren; nur Bugfixes bis v1.0.0 erlaubt
- Aktuelle Version wird als `v0.32.0-rc` getaggt vor Pilotbeginn

## [0.31.0] - 2026-03-16

### Added (M31 – Final Gap Check gegen Reference-Projekt)
- `docs/reference-gap-analysis.md` – vollständige Vergleichsmatrix Reference vs. Astra in 7 Domänen (User & Access, Workload, Files/Backups/Databases, Fleet/Infra, Automation, Templates, Extensibility)
- `docs/v1-scope.md` – verbindliches Scope-Dokument: Was ist v1.0, was bewusst nicht, Known Limitations, Roadmap, Pilot-Empfehlung
- Terminologie-Mapping dokumentiert (Node→Agent, Allocation→Endpoint, Egg→Blueprint, Schedule→Routine, Subuser→Collaborator, Server→Instance)
- Technische Gleichwertigkeitsbewertung (übertroffen / gleichwertig / schwächer) für alle relevanten Bereiche
- Priorisierte Lückenliste (P0/P1/P2) – keine P0-Lücken identifiziert
- Bewusste Astra-Abweichungen dokumentiert (Fleet Monitoring, Maintenance Mode, Job-Dashboard, Upgrade-Framework, TypeScript Frontend)

### Analysis Results (M31)
- **Keine P0-Lücken**: Alle Kernfunktionen sind implementiert
- **P1** (kurz nach v1.0): Blueprint Import/Export, API-Key-Scoping, OAuth/SSO, File-Upload HTTP, Mehrere Docker-Images pro Blueprint
- **P2** (bewusst später): Plugin-System, Blueprint-Vererbung, Mount System, i18n, Prometheus-Integration
- **Empfehlung**: Astra v1.0 ist freigabereif für Pilotbetrieb mit dokumentierten Einschränkungen

## [0.30.0] - 2026-03-16

### Added (M30 – Echte SFTP-/SSH-Key-Authentifizierung)
- Permission `file.sftp` im Collaborator-Permission-Katalog (`permissions.py`) – steuert SFTP-Zugang fuer Collaborators
- `backend/app/domain/ssh_keys/auth_service.py` – zentraler SFTP-Auth-Service:
  - `authorize_ssh_key_access(instance_uuid, username, public_key, fingerprint)` – vollstaendige Auth-Entscheidung
  - `find_key_by_fingerprint(user_id, fingerprint)` / `find_key_by_public_key(user_id, public_key)` – Key-Matching
  - `find_user_key(user_id, public_key, fingerprint)` – kombiniertes Key-Lookup (public_key bevorzugt, FP serverseitig berechnet)
  - Unterscheidung: `ok`, `user_unknown`, `instance_not_found`, `key_unknown`, `permission_denied`, `instance_suspended`, `malformed_request`
- Agent-API-Endpunkt `POST /agent/sftp-auth`:
  - Validiert Request (username, instance_uuid, public_key/fingerprint)
  - Ruft `authorize_ssh_key_access()` auf
  - Antwortet mit `allowed: true/false` und Permissions oder Ablehnungsgrund
  - Gibt keine sensiblen Daten (Key-Klartext, Passwort-Hash) zurueck
- Activity-Events `ssh_key:auth_success` und `ssh_key:auth_failed` (Events-Katalog + Webhook-Katalog)
- Fehler-Events loggen nur Fingerprint (kein Public-Key-Klartext)
- Suspension-Guard aus M29 aktiv in SFTP-Auth (suspendierte Instances werden blockiert)
- Frontend `SshKeysPage.tsx`: Info-Box aktualisiert – Keys werden jetzt fuer SFTP genutzt, Owner/Collaborator-Regeln erklaert
- Dokumentation `docs/ssh-sftp-auth.md`: Key-Typen, Berechtigungsmodell, API-Format, Reason-Codes, Sicherheitshinweise
- Testsuite `backend/test_m30.py` (Key-Matching, Auth-Service alle Deny/Allow-Pfade, Agent-API, Security, Events, Regression M10–M29)

### Notes
- Kein vollstaendiger SSH-Server in Astra – Astra ist rein die Kontrollinstanz fuer Auth-Entscheidungen
- Private Keys werden **nie** gespeichert, verarbeitet oder geloggt
- Fingerprints werden serverseitig berechnet (dem Agent wird kein Fingerprint blind vertraut)
- Owner haben automatisch SFTP-Zugriff; Collaborators benoetigen `file.sftp`

## [0.29.0] - 2026-03-16

### Added (M29 – Suspension / Unsuspend & Administrative Instance Locks)
- `Instance`-Modell um Suspension-Felder erweitert: `suspended_reason` (String 500), `suspended_at` (DateTime), `suspended_by_user_id` (FK users)
- SQLAlchemy-Relationships: `owner` mit `foreign_keys=[owner_id]` und `suspended_by` mit `foreign_keys=[suspended_by_user_id]` (Ambiguity-Fix)
- `to_dict()` gibt `suspended_reason`, `suspended_at`, `suspended_by_user_id` zurueck
- Alembic-Migration `k1f2g3h4i5j6_milestone29_suspension` fuer die drei neuen Spalten
- Service-Funktionen: `suspend_instance()`, `unsuspend_instance()`, `is_instance_suspended()` (idempotent)
- Activity-Events: `instance:suspended`, `instance:unsuspended`
- Webhook-Katalog um Suspension-Events erweitert
- Zentraler Guard `_require_not_suspended()` in `client/routes.py` schuetzt 13+ operative Endpunkte (Power, Reinstall, Build, Variables, Sync, WebSocket, File-Write/-Delete/-Mkdir/-Rename/-Compress/-Decompress, Backup-Create/-Restore/-Delete, DB-Create/-RotatePassword/-Delete, Routine-Execute) mit HTTP 409
- Admin-API: `POST /api/admin/instances/<uuid>/suspend` und `/unsuspend` (require_admin)
- Frontend: TypeScript `Instance`-Interface um `suspended_reason`, `suspended_at`, `suspended_by_user_id` erweitert
- Frontend: `api.suspendInstance(uuid, reason?)` und `api.unsuspendInstance(uuid)` in `api.ts`
- Frontend: Suspend/Unsuspend `ConfirmButton` in `AdminInstancesPage` (status-abhaengig)
- Frontend: Suspension-Banner in `InstanceDetailPage` (orange Warnung mit Grund und Hinweis)
- Vollstaendige Testsuite `backend/test_m29.py` (Service, Admin-API, Access-Blocking 13 Endpunkte, Events, Regression M10–M28)

### Notes
- Suspension ist rein administrativ; der Container-Status (`container_state`) bleibt unveraendert
- Operative Aktionen werden mit 409 blockiert solange `status == "suspended"`

## [0.28.0] - 2026-03-16

### Added (M28 – SSH Keys & SFTP Access Management)
- `UserSshKey`-Domain-Modell mit Feldern `id`, `user_id`, `name`, `fingerprint`, `public_key`, `created_at`, `updated_at`
- Alembic-Migration `j0e1f2g3h4i5_milestone28_ssh_keys` mit Foreign Key auf `users` und Unique Constraint `(user_id, fingerprint)`
- SSH-Public-Key-Validator (`backend/app/domain/ssh_keys/validator.py`): Format-Pruefung und serverseitige SHA256-Fingerprint-Berechnung
  - Unterstuetzte Typen: `ssh-ed25519`, `ssh-rsa`, `ecdsa-sha2-nistp256/384/521`
- SSH-Key-Service mit `list_user_ssh_keys`, `create_user_ssh_key`, `update_user_ssh_key_name`, `delete_user_ssh_key`
- Client-API-Endpunkte: `GET/POST /api/client/account/ssh-keys`, `PATCH/DELETE /api/client/account/ssh-keys/<id>`
- Activity-Events: `ssh_key:created`, `ssh_key:updated`, `ssh_key:deleted`
- Webhook-Katalog um SSH-Key-Events erweitert
- Frontend: `SshKeysPage` mit Key-Liste, Hinzufuegen-Formular und Delete-Bestaetigung
- Frontend: `SshKeyEntry` / `SshKeyCreateRequest` TypeScript-Interfaces und API-Funktionen in `api.ts`
- Route `/account/ssh-keys` im AppRouter, Navigationseintrag "SSH Keys" in PageLayout
- Vollstaendige Testsuite `backend/test_m28.py` (Modell, Validierung, Fingerprint, Service, API, Events, Regression)

### Notes
- SFTP-Key-Authentifizierung (echte schluesselbasierte SSH-Logins) wird in M29 aktiviert
- Fingerprints werden ausschliesslich serverseitig berechnet (OpenSSH SHA256-Format)

## [0.27.0-rc1] - 2026-03-14

### Added
- RC-Checkliste, manuelle Abnahmedoku, Known-Limitations-Doku
- Umfassende Security-/Serialization-/Failure-Tests (test_m27.py)

### Improved
- Fehlerbehandlung bei Runner-/Queue-Ausfall gehaertet
- Security-Checks: Secrets leaken nicht in Responses
- Logging-Konsistenz verbessert

## [0.26.0] - 2026-03-14

### Added
- Zentrale UI-Komponentenbibliothek (StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, PageLayout)
- Gemeinsame Styles und Konventionen
- PageLayout mit Navigation (Core/Operations/Integrations)
- UI-Konventionen-Dokumentation

### Improved
- DashboardPage komplett auf neue Komponenten migriert
- InstanceDetailPage mit PageLayout und StatusBadge
- Konsistentere Farben und Status-Darstellungen

## [0.25.0] - 2026-03-14

### Added
- Agent Maintenance-Modus (maintenance_mode, maintenance_reason, maintenance_started_at)
- Maintenance-Service (enable/disable, idempotent)
- Deployment-Guard: Maintenance-Agents blockieren neue Instances (409)
- Activity-/Webhook-Events (agent:maintenance_enabled/disabled)
- Admin-API: POST/DELETE/PATCH /api/admin/agents/{id}/maintenance
- Fleet-Monitoring zeigt Maintenance-Status
- Frontend: Maintenance-Toggle in Fleet Monitoring

## [0.24.0] - 2026-03-14

### Added
- Zentrale Versionsquelle (`backend/app/version.py`)
- Build-/Release-Metadaten (SHA, Datum, Ref via Umgebungsvariablen)
- DB-Migrationsstatus-Pruefung (Alembic Head vs. applied)
- Upgrade-Preflight-Check (Config, DB, Migrationen, Redis)
- Ops-Endpunkte: `/ops/version`, `/ops/upgrade-status`, `/ops/preflight`
- Admin-API: `/api/admin/system/version`, `/api/admin/system/upgrade-status`, `/api/admin/system/preflight`
- Frontend: System-Info-Seite (`/admin/system`)
- CLI-Befehle: `version`, `preflight`, `upgrade-status`
- Upgrade-/Rollback-Dokumentation (`docs/upgrade-guide.md`)

## [0.23.0] - 2026-03-14

### Added
- Job-/Queue-Infrastruktur (`backend/app/infrastructure/jobs/`)
- Job-Tracking-Modell (`JobRecord`) mit Status-Verfolgung
- Queue-Backends: SyncQueue (Dev), ThreadQueue, RedisQueue (Prod)
- Webhook-Dispatch ueber Job-Queue (statt ad-hoc Threading)
- Routine-Ausfuehrung non-blocking via Jobs
- Admin-API fuer Jobs: `/api/admin/jobs`, `/api/admin/jobs/summary`
- Frontend: Jobs-Dashboard (`/admin/jobs`)
- Worker-Entrypoint: `python cli.py worker`
- 5 Job-Typen: webhook_dispatch, routine_execute, routine_action, agent_health_check, instance_sync

## [0.22.0] - 2026-03-14

### Added
- Agent Fleet Monitoring mit Kapazitaetsmodell
- Health-Status pro Agent (healthy, stale, degraded, unreachable)
- Kapazitaets-/Auslastungsberechnung (Memory, Disk, CPU)
- Overallocation-Unterstuetzung pro Agent
- Admin-API: `/api/admin/agents/monitoring`, `/api/admin/fleet/summary`
- Frontend: Fleet-Monitoring-Dashboard (`/admin/agents/monitoring`)

## [0.21.0] - 2026-03-14

### Added
- Deployment & Operations Readiness
- Strukturiertes Logging, ProxyFix, Security Headers
- Rate Limiting, Bootstrap-CLI, Ops-Endpunkte

## [0.20.0] - 2026-03-14

### Added
- Agent Health-Tracking (`last_seen_at`, `is_stale()`)
- Production Hardening (Lifecycle, Runtime)

## [0.19.0] - 2026-03-14

### Added
- Auth: JWT, Sessions, API Keys, MFA

## [0.18.0] - 2026-03-14

### Added
- Database Provisioning

## [0.17.0] - 2026-03-14

### Added
- Routines & Actions

## [0.16.0] - 2026-03-14

### Added
- Instance Lifecycle (Reinstall, Build Config, Sync)

## [0.15.0] - 2026-03-14

### Added
- Container State Management

## [0.14.0] - 2026-03-14

### Added
- Collaborators & Permissions

## [0.13.0] - 2026-03-14

### Added
- Backups

## [0.12.0] - 2026-03-14

### Added
- Files & Console

## [0.11.0] - 2026-03-14

### Added
- Wings-Integration

## [0.10.0] - 2026-03-14

### Added
- Webhooks & Activity Logging
