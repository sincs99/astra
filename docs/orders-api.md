# Produkte und Bestellungen (M44)

Phase 4, Schritte 3 und 4 aus [phase4-plan.md](phase4-plan.md): Pakete definieren, Kunden bestellen,
der Admin bestätigt die Zahlung manuell, die Instance wird automatisch platziert und angelegt.
Zahlungsanbieter und Abrechnungs-Tick (Ablauf → Suspend → Löschen) sind noch nicht umgesetzt.

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
dabei nicht doppelt verbucht. Ein erneuter Aufruf bei einer aktiven Bestellung ändert nichts.

## Status

| Status | Bedeutung |
|---|---|
| `pending_payment` | angelegt, noch nicht bezahlt |
| `awaiting_provisioning` | bezahlt, Instance fehlt noch (kein Platz) |
| `active` | bezahlt, Instance läuft |
| `past_due` | Laufzeit abgelaufen, Instance suspendiert (kommt mit dem Billing-Tick) |
| `cancelled` | offene Bestellung vom Kunden storniert |
| `expired` | beendet (kommt mit dem Billing-Tick) |

Kündigt ein Kunde eine **aktive** Bestellung, wird `cancel_at_period_end` gesetzt. Der Server läuft
bis zum Laufzeitende weiter.

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

Activity- und Webhook-Events: `order:created`, `order:paid`, `order:provision_failed`, `order:cancelled`.

## Noch nicht enthalten

Billing-Tick (Ablauf, Suspend, Löschfrist, Verlängerung), Zahlungsanbieter mit Webhook, Mails zu
Bestellungen, Rechnungen mit Umsatzsteuer, Frontend (Shop, Bestellübersicht, Admin-Seiten). Rechtliche
Voraussetzungen siehe [phase4-plan.md](phase4-plan.md).
