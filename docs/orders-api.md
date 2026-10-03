# Produkte und Bestellungen (M44)

Phase 4, Schritte 3 und 4 aus [phase4-plan.md](phase4-plan.md): Pakete definieren, Kunden bestellen,
der Admin bestätigt die Zahlung manuell, die Instance wird automatisch platziert und angelegt.
Der Billing-Tick (Ablauf → Suspend → Löschen, M46) und die Online-Zahlung mit Stripe (M48) sind umgesetzt.
Standard bleibt die manuelle Zahlung.

## Ablauf

1. Admin legt ein **Produkt** an (Blueprint, RAM/Disk/CPU, Preis in Cent, Laufzeit in Tagen).
2. Kunde ruft `GET /api/client/products` (öffentlich) und bestellt mit `POST /api/client/orders`.
   Die Bestellung ist `pending_payment` und enthält einen **Schnappschuss** von Preis, Laufzeit und
   Ressourcen. Spätere Produktänderungen betreffen sie nicht. Ressourcen kommen nie vom Kunden.
3. Zahlung geht außerhalb von Astra ein (z. B. Überweisung). Der Admin ruft
   `POST /api/admin/orders/{uuid}/mark-paid` auf.
4. Astra wählt per `pick_agent` einen passenden Node (aktiv, nicht in Wartung, freier Endpoint,
   genug Kapazität), legt die Instance für den Kunden an und setzt die Bestellung auf `active`
   (`current_period_end` = Zahlung + Laufzeit).

Ist nach der Zahlung kein Node frei, bleibt die Bestellung bezahlt, aber `awaiting_provisioning`.
Der Admin schafft Platz (Endpoints, Kapazität) und ruft `mark-paid` erneut auf. Die Zahlung wird
dabei nicht doppelt verbucht.

## Verlängerung

`mark-paid` auf einer `active` oder `past_due` Bestellung verlängert um eine Laufzeit. Dafür ist
`payment_reference` **Pflicht** (sonst 400): Dieselbe Referenz verlängert nie zweimal, ein Doppelklick
oder eine Wiederholung ist ein No-op. Das neue Ende zählt ab `max(jetzt, bisheriges Ende)`: Vorauszahlungen
verfallen nicht, eine verspätete Zahlung verschenkt aber keine Zeit. Eine Sperre wegen überfälliger Zahlung
wird aufgehoben, eine Admin-Sperre aus anderem Grund (z. B. Missbrauch) bleibt bestehen. Eine vorgemerkte
Kündigung bleibt erhalten.

## Status

| Status | Bedeutung |
|---|---|
| `pending_payment` | angelegt, noch nicht bezahlt |
| `awaiting_provisioning` | bezahlt, Instance fehlt noch (kein Platz) |
| `active` | bezahlt, Instance läuft |
| `past_due` | Laufzeit abgelaufen, Instance gesperrt und gestoppt, Karenzzeit läuft |
| `cancelled` | offene Bestellung vom Kunden storniert |
| `expired` | beendet, Instance gelöscht (Tick oder manuelles Löschen der Instance) |

Kündigt ein Kunde eine **aktive** Bestellung, wird `cancel_at_period_end` gesetzt. Der Server läuft
bis zum Laufzeitende weiter.

## Billing-Tick

`python cli.py billing-tick` setzt die Laufzeiten durch. Er ist idempotent und für Cron oder einen
Compose-Service gedacht (alle 5 Minuten reichen). Ausgabe: eine JSON-Zeile
`{"checked", "past_due", "expired", "reminded", "renewed", "errors": [...]}`, Exit-Code 1 bei Fehlern.

| Situation | Aktion |
|---|---|
| `active`, Laufzeit abgelaufen | `past_due`: Instance suspendiert (Grund „Zahlung überfällig“), synchronisiert und auf dem Node beendet (`kill`), Mail |
| `past_due` länger als `BILLING_GRACE_DAYS` (Standard 7) | Instance gelöscht (`force`), `expired`, Mail |
| Kündigung zum Laufzeitende, Laufzeit abgelaufen | sofort gelöscht, `expired` (ohne Karenzzeit) |
| Instance existiert nicht mehr | `expired`, ohne Runner-Aufruf |
| `BILLING_REMINDER_DAYS` (Standard 3) vor Laufzeitende | Mail, Event `order:reminder`, höchstens einmal pro Bestellung und Laufzeit; `0` schaltet ab. Normale Bestellungen (bezahlt, Laufzeit länger als das Fenster): „Laufzeit endet bald“. Gekündigte: einmalig „Server wird am X gelöscht“ |
| Kostenloses Paket (`price_cents = 0`), Laufzeit abgelaufen | wird automatisch verlängert (`renewed`, Referenz `free-auto:...`), keine Sperre, keine Mail; nach Kündigung läuft es zum Laufzeitende aus |

Sicherheiten:

- Die Karenzzeit zählt ab `past_due_at` (dem Moment, in dem der Tick die Bestellung überfällig gesetzt hat),
  nicht ab dem Laufzeitende. Fällt der Tick mehrere Tage aus, verlieren Kunden ihre Karenzzeit nicht.
- Eine bestehende Admin-Sperre wird nicht überschrieben.
- Läuft gerade eine Installation, ein Transfer oder eine Wiederherstellung, wartet der Tick bis zu einen
  Tag. Danach sperrt er trotzdem.
- Jede Bestellung wird einzeln committed. Ein Fehler (steht in `errors`) blockiert die anderen nicht, die
  Bestellung wird im nächsten Tick erneut versucht.
- Pending-, bezahlt-unbereitgestellte und beendete Bestellungen fasst der Tick nie an.

Wird eine Instance direkt gelöscht (Admin oder Kunde), setzt Astra die verknüpfte lebende Bestellung auf
`expired`. Ein bereits bezahlter Rest der Laufzeit wird nicht erstattet. Die Bestellung zeigt
`scheduled_deletion_at`, wann der Server gelöscht wird (Ende der Karenzzeit bzw. Laufzeitende bei Kündigung).

## Zeitstempel (M49)

Alle Zeitstempel der API sind UTC mit Zeitzonen-Suffix, z. B. `2026-10-03T12:00:00+00:00`. Browser lesen
Strings ohne Suffix sonst als Ortszeit. Intern liefert die Datenbank naive UTC-Werte, `iso_utc()`
(`app/utils/timeutil.py`) hängt den Suffix an. Neue `to_dict()`-Methoden müssen `iso_utc(...)` statt
`.isoformat()` verwenden; `test_m49.py` ruft alle GET-Routen auf und schlägt bei einem Zeitstempel ohne Suffix fehl.

## Zahlungsanbieter (M48)

`PAYMENT_PROVIDER` wählt den Zahlungsweg:

| Wert | Verhalten |
|---|---|
| `manual` (Standard) | Zahlung geht außerhalb ein, der Admin bestätigt per `mark-paid`. `POST /orders/{uuid}/checkout` liefert 409 mit Hinweis auf die Überweisung |
| `stripe` | Stripe Checkout (`mode=payment`) für Kunden, Zahlung wird per Webhook automatisch verbucht |

`GET /api/client/billing-info` (öffentlich) liefert `{"payment_provider", "online_payment"}`, damit der Shop
„Jetzt bezahlen“ nur bei aktivem Stripe zeigt.

### Ablauf mit Stripe

1. Kunde ruft `POST /api/client/orders/{uuid}/checkout` auf und bekommt `{"checkout_url"}` (nur `https://`).
   Fehler tragen einen stabilen `code`: 409 `manual` (Zahlungsweg ist die Überweisung), 409 `invalid_status`,
   409 `nothing_to_pay`, 409 `unsupported_currency`, 502 `provider_unavailable` / `provider_error`. Erlaubt bei
   `pending_payment` (Erstzahlung) sowie `active`/`past_due` (Verlängerung). Jeder Aufruf erzeugt eine neue
   Checkout-Session; jede bezahlte Session verlängert um eine Laufzeit (Vorauszahlung möglich).
2. Nach dem Bezahlen schickt Stripe `checkout.session.completed` an `POST /api/payments/stripe`. Astra
   verbucht wie bei `mark-paid`: Erstbereitstellung oder Verlängerung, `payment_reference` = PaymentIntent-ID.
3. Stripe leitet den Kunden zu `{FRONTEND_URL}/orders?paid=<uuid>` (Abbruch: `?cancelled=<uuid>`) zurück.
   Die Bestellung kann einen Moment brauchen, bis der Webhook angekommen ist; die Seite sollte den Status
   erneut abfragen.

### Webhook-Regeln

- Ohne Login, geschützt durch die Signaturprüfung (`Stripe-Signature`, Toleranz 5 Minuten). Fehlende oder
  falsche Signatur: 400.
- **Idempotenz:** Jede Event-ID wird einmal verarbeitet (Tabelle `payment_events`); dieselbe Zahlung wird
  zusätzlich über `payment_references` nie doppelt verbucht (auch nicht bei `completed` und
  `async_payment_succeeded` für dieselbe Zahlung). Bricht die Verarbeitung ab (500), wiederholt Stripe die
  Zustellung und sie wird erneut versucht.
- `payment_status` muss `paid` sein (bei verzögerten Zahlarten wie SEPA kommt die Freischaltung mit
  `checkout.session.async_payment_succeeded`). Alle anderen Ereignisse: 200 und ignoriert.
- Weicht **Betrag oder Währung** von der Bestellung ab, wird nichts freigeschaltet (Status `mismatch`,
  Activity-Event `order:payment_unapplied`).
- Ist die Bestellung nicht mehr bezahlbar (storniert oder beendet), bleibt die Zahlung unverbucht (`unapplied`)
  und es entsteht `order:payment_unapplied`: **Erstattung im Stripe-Dashboard prüfen.**
- Ist nach der Zahlung kein Node frei, antwortet der Webhook trotzdem 200 (Zahlung ist verbucht, Bestellung
  `awaiting_provisioning`); der Admin stellt später per `mark-paid` bereit.
- Nur Währungen mit Nachkommastellen werden unterstützt (kein JPY, KRW usw.).

### Einrichtung

1. In Stripe zuerst den **Test-Modus** nutzen (Schlüssel `sk_test_...`).
2. Webhook-Endpunkt anlegen: URL `https://<PANEL_DOMAIN>/api/payments/stripe`, Ereignisse
   `checkout.session.completed` und `checkout.session.async_payment_succeeded`. Das Signing-Secret
   (`whsec_...`) kopieren.
3. In der Backend-Umgebung setzen (nicht ins Repository): `PAYMENT_PROVIDER=stripe`, `STRIPE_SECRET_KEY`,
   `STRIPE_WEBHOOK_SECRET`; `FRONTEND_URL` muss die öffentliche Panel-URL sein. Backend neu starten.
   In Produktion meldet der Start einen kritischen Konfigurationsfehler, wenn Stripe ohne Schlüssel gewählt ist.
4. Lokal testen mit der Stripe CLI: `stripe listen --forward-to localhost:5000/api/payments/stripe`
   (gibt ein temporäres `whsec_...` aus) und eine Testzahlung mit Karte `4242 4242 4242 4242`.
5. Erst nach erfolgreichem Test-Durchlauf auf Live-Schlüssel wechseln. Rechtliche Voraussetzungen
   (Gewerbe, AGB, Widerruf, Rechnungen) siehe [phase4-plan.md](phase4-plan.md).

## Regeln und Grenzen

- Höchstens 5 offene (`pending_payment`) Bestellungen pro Kunde.
- `max_instances_per_user` begrenzt Bestellungen je Paket und Kunde (offene und aktive zählen).
- **Kostenlose Produkte** (`price_cents = 0`) brauchen `max_instances_per_user` und werden sofort
  bereitgestellt (Zahlungsreferenz `free`). Fehlt der Platz, bleibt die Bestellung `awaiting_provisioning`.
- Ist `EMAIL_VERIFICATION_REQUIRED` aktiv, können nur Kunden mit bestätigter E-Mail bestellen (403, `email_not_verified`).
- Ein Produkt mit Bestellungen lässt sich nicht löschen (409), nur deaktivieren. Ein Blueprint, der von
  Produkten verwendet wird, ebenfalls nicht.

## Endpunkte

| Methode und Pfad | Wer | Zweck |
|---|---|---|
| `GET /api/client/products` | öffentlich | aktive Pakete (ohne interne Felder) |
| `POST /api/client/orders` | Kunde | `{product_id, name?}` bestellen |
| `GET /api/client/orders`, `/{uuid}` | Kunde | eigene Bestellungen, inkl. Instance und Verbindungsadresse |
| `POST /api/client/orders/{uuid}/cancel` | Kunde | stornieren bzw. zum Laufzeitende kündigen |
| `POST /api/client/orders/{uuid}/checkout` | Kunde | Online-Zahlung starten → `{checkout_url}` (nur mit Stripe) |
| `GET /api/client/billing-info` | öffentlich | aktiver Zahlungsweg |
| `POST /api/payments/stripe` | Stripe | Webhook (Signatur statt Login) |
| `GET/POST /api/admin/products`, `GET/PATCH/DELETE /{id}` | Admin | Pakete verwalten |
| `GET /api/admin/orders?status=&user_id=`, `/{uuid}` | Admin | alle Bestellungen |
| `POST /api/admin/orders/{uuid}/mark-paid` | Admin | `{payment_reference?}` Zahlung bestätigen, Instance bereitstellen |

Activity- und Webhook-Events: `order:created`, `order:paid`, `order:provision_failed`, `order:cancelled`,
`order:past_due`, `order:renewed`, `order:expired`, `order:reminder`, `order:payment_unapplied`.

## Noch nicht enthalten

Mails zu Bestellungen beim Anlegen und Bezahlen, Erstattungen (manuell im Stripe-Dashboard),
Rechnungen mit Umsatzsteuer, Frontend (Shop, Bestellübersicht, Admin-Seiten). Rechtliche
Voraussetzungen siehe [phase4-plan.md](phase4-plan.md).
