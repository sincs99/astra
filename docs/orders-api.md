# Produkte und Bestellungen (M44)

Phase 4, Schritte 3 und 4 aus [phase4-plan.md](phase4-plan.md): Pakete definieren, Kunden bestellen,
der Admin bestätigt die Zahlung manuell, die Instance wird automatisch platziert und angelegt.
Der Billing-Tick (Ablauf → Suspend → Löschen, M46) ist umgesetzt, ein Zahlungsanbieter noch nicht.

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
| `BILLING_REMINDER_DAYS` (Standard 3) vor Laufzeitende | Erinnerungsmail, Event `order:reminder`, höchstens einmal pro Bestellung und Laufzeit; nur bezahlte Bestellungen ohne Kündigung, Laufzeit länger als das Fenster; `0` schaltet ab |
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
| `GET/POST /api/admin/products`, `GET/PATCH/DELETE /{id}` | Admin | Pakete verwalten |
| `GET /api/admin/orders?status=&user_id=`, `/{uuid}` | Admin | alle Bestellungen |
| `POST /api/admin/orders/{uuid}/mark-paid` | Admin | `{payment_reference?}` Zahlung bestätigen, Instance bereitstellen |

Activity- und Webhook-Events: `order:created`, `order:paid`, `order:provision_failed`, `order:cancelled`,
`order:past_due`, `order:renewed`, `order:expired`, `order:reminder`.

## Noch nicht enthalten

Zahlungsanbieter mit Webhook, Mails zu Bestellungen beim Anlegen und Bezahlen,
Rechnungen mit Umsatzsteuer, Frontend (Shop, Bestellübersicht, Admin-Seiten). Rechtliche
Voraussetzungen siehe [phase4-plan.md](phase4-plan.md).
