# Phase 4: Pakete, Bestellung, Abrechnung (Plan)

> Stand 2026-10-03. Ergebnis der Backend-Analyse nach Abschluss von Phase 2. Noch nichts davon ist
> umgesetzt; dieses Dokument legt Reihenfolge und Lücken fest, damit die Arbeit verteilt werden kann.

## Ziel

Ein Kunde registriert sich, wählt ein Paket, bezahlt und bekommt automatisch einen Gameserver.
Läuft die Zahlung aus, wird der Server suspendiert und nach einer Frist gelöscht. Der Admin
definiert Pakete und sieht Bestellungen.

## Was heute fehlt

| Lücke | Befund | Folge |
|---|---|---|
| Kapazitätsprüfung | `create_instance` prüft die Agent-Kapazität nicht. `get_effective_memory/disk/cpu` und `get_utilization_summary` existieren, werden aber nicht genutzt | Ein Node lässt sich überbuchen |
| Instanz löschen | Es gibt keinen Löschpfad (kein `DELETE`, keine `delete_instance` im Service). Nur der Runner-Adapter kann löschen | Endpoints werden nie frei, Ablauf → Löschen ist unmöglich |
| Zeitsteuerung | Kein periodischer Tick. Der Worker verarbeitet nur die Job-Queue | Ablauf, Mahnung, Löschfrist können nicht automatisch laufen |
| Kunden-Erstellung | Instanzen entstehen nur über `/api/admin` | Kein Self-Service |
| Produkte, Bestellungen, Zahlung | Keine Modelle, keine Endpunkte | Kein Geschäftsmodell |

## Datenmodell (Vorschlag)

**products:** `name`, `description`, `blueprint_id`, `memory`, `disk`, `cpu` (+ `swap`, `io` mit Defaults),
`price_cents`, `currency`, `billing_period_days`, `active`, optional `max_instances_per_user`.

**orders:** `user_id`, `product_id`, `instance_id`, `status`
(`pending_payment` | `active` | `past_due` | `cancelled` | `expired`), `current_period_end`,
`cancel_at_period_end`, `payment_reference`, `created_at`.

Regeln: Ressourcen kommen immer aus dem Produkt, nie vom Kunden. Eine Instanz wird erst nach
bestätigter Zahlung angelegt (Alternative: sofort anlegen, aber suspendiert).

## Platzierung

`pick_agent(product)`: aktive Agents ohne Wartungsmodus, mit freiem Endpoint und genug freiem
RAM, Disk und CPU (effektive Kapazität inkl. Overalloc minus Summe der zugewiesenen Instanzen).
Auswahl nach geringster Auslastung. Die Endpoint-Wahl selbst existiert bereits (erster freier Port).

## Zeitsteuerung

Einfachste tragfähige Variante: `python cli.py billing-tick`, idempotent, alle paar Minuten per Cron
oder als Compose-Service. Aufgaben: abgelaufene Bestellungen suspendieren (`suspend_instance`, M29),
nach Frist löschen (`delete_instance`, neu), Verlängerung hebt Suspension auf (`unsuspend_instance`),
Mails über `mail.py`.

## Zahlung

Provider-Abstraktion mit einer Stripe-Implementierung: Checkout-Session erzeugen, Webhook
`/api/payments/stripe` mit Signaturprüfung und Idempotenz über die Event-ID. Davor als erster
Schritt ein manueller Admin-Weg "Bestellung als bezahlt markieren", um Produkt, Bestellung und
Ablauf ohne Zahlungsanbieter zu testen.

## Reihenfolge

1. Kapazitätsprüfung und `pick_agent` (auch ohne Phase 4 nötig, verhindert Überbuchung)
2. `delete_instance` mit Runner-Delete, Endpoint-Freigabe, Aufräumen von Backups, Datenbanken,
   Collaborators, Routinen, Activity-Log; Admin-Endpunkt `DELETE /api/admin/instances/{uuid}`
3. Produkt-Modell, Migration, Admin-CRUD, öffentliches `GET /api/client/products`
4. Bestellung `POST /api/client/orders` mit manuellem "bezahlt" durch den Admin
5. Billing-Tick
6. Stripe
7. Frontend: Shop, Bestellübersicht, Admin-Produkte und Bestellungen

## Rahmenbedingungen außerhalb des Codes

Gewerbeanmeldung, Impressum, AGB, Widerrufsbelehrung, Rechnungen mit Umsatzsteuer, Datenschutz.
Ohne das darf kein Geld angenommen werden, unabhängig vom technischen Stand.
