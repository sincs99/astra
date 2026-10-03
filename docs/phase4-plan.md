# Phase 4: Pakete, Bestellung, Abrechnung (Plan)

> Stand 2026-10-03. **Backend umgesetzt (M42 bis M49), Frontend vorhanden.** Dieses Dokument war der Plan
> nach der Backend-Analyse zu Phase 2 und hält Ausgangslage und Reihenfolge fest. Die tatsächliche
> Schnittstelle steht in [orders-api.md](orders-api.md), Einschränkungen in
> [known-limitations.md](known-limitations.md).

## Umsetzungsstand

| Schritt | Status | Meilenstein | Absicherung |
|---|---|---|---|
| 1. Kapazitätsprüfung, `pick_agent` | umgesetzt | M42 | `test_m42.py` |
| 2. `delete_instance` (Admin und Besitzer) | umgesetzt | M43 | `test_m43.py` |
| 3. Produkt-Modell, Admin-CRUD, öffentliche Liste | umgesetzt | M44 | `test_m44.py` |
| 4. Bestellung mit manuellem „bezahlt“ | umgesetzt | M44 | `test_m44.py` |
| 5. Billing-Tick (Ablauf, Karenz, Löschung, Verlängerung, Erinnerung) | umgesetzt | M46 | `test_m46.py` |
| 6. Stripe (Checkout, Webhook, Idempotenz) | umgesetzt, nur mit gemockten Aufrufen getestet | M48 | `test_m48.py` |
| 7. Frontend: Shop, Bestellübersicht, Admin-Produkte und -Bestellungen | umgesetzt (Frontend-Session) | – | Frontend-Tests |
| Zusätzlich: einheitliche UTC-Zeitstempel | umgesetzt | M49 | `test_m49.py` |
| Zusätzlich: E-Mail-Verifizierung vor der Bestellung | umgesetzt | M38 | `test_m38.py` |

**Noch offen vor einem echten Betrieb mit Geld:** Stripe einmal im Test-Modus mit Stripe CLI durchspielen
(echte Aufrufe wurden nie ausgeführt), PostgreSQL-Durchlauf der Migrationskette, die rechtlichen
Rahmenbedingungen unten und die Punkte aus „Abrechnung und Shop“ in den Known Limitations.

## Ziel

Ein Kunde registriert sich, wählt ein Paket, bezahlt und bekommt automatisch einen Gameserver.
Läuft die Zahlung aus, wird der Server suspendiert und nach einer Frist gelöscht. Der Admin
definiert Pakete und sieht Bestellungen.

## Ausgangslage (vor der Umsetzung)

| Lücke | Befund | Folge | Status |
|---|---|---|---|
| Kapazitätsprüfung | `create_instance` prüfte die Agent-Kapazität nicht | Ein Node ließ sich überbuchen | behoben (M42) |
| Instanz löschen | Es gab keinen Löschpfad, nur der Runner-Adapter konnte löschen | Endpoints wurden nie frei, Ablauf → Löschen war unmöglich | behoben (M43) |
| Zeitsteuerung | Kein periodischer Tick | Ablauf, Mahnung, Löschfrist konnten nicht automatisch laufen | behoben (M46, Compose-Service `billing`) |
| Kunden-Erstellung | Instanzen entstanden nur über `/api/admin` | Kein Self-Service | behoben (M44, Bestellung statt Direkterstellung) |
| Produkte, Bestellungen, Zahlung | Keine Modelle, keine Endpunkte | Kein Geschäftsmodell | behoben (M44, M48) |

## Datenmodell (Vorschlag, umgesetzt mit Abweichungen)

> Abweichungen in der Umsetzung: zusätzlicher Status `awaiting_provisioning` (bezahlt, aber noch keine Instance);
> Bestellungen tragen einen Schnappschuss von Preis, Laufzeit und Ressourcen sowie `payment_references`,
> `past_due_at` und `reminded_for_period_end`; Zahlungsereignisse stehen in `payment_events`. Die
> Felder und Regeln stehen in [orders-api.md](orders-api.md).

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

1. Kapazitätsprüfung und `pick_agent` (auch ohne Phase 4 nötig, verhindert Überbuchung) – **umgesetzt**
2. `delete_instance` mit Runner-Delete, Endpoint-Freigabe, Aufräumen von Backups, Datenbanken,
   Collaborators, Routinen, Activity-Log; Admin-Endpunkt `DELETE /api/admin/instances/{uuid}` – **umgesetzt**
3. Produkt-Modell, Migration, Admin-CRUD, öffentliches `GET /api/client/products` – **umgesetzt**
4. Bestellung `POST /api/client/orders` mit manuellem "bezahlt" durch den Admin – **umgesetzt**
5. Billing-Tick – **umgesetzt**
6. Stripe – **umgesetzt**
7. Frontend: Shop, Bestellübersicht, Admin-Produkte und Bestellungen – **umgesetzt**

## Rahmenbedingungen außerhalb des Codes

Gewerbeanmeldung, Impressum, AGB, Widerrufsbelehrung, Rechnungen mit Umsatzsteuer, Datenschutz.
Ohne das darf kein Geld angenommen werden, unabhängig vom technischen Stand. Astra erstellt keine
Rechnungen und rechnet keine Umsatzsteuer; Rechnungsstellung muss außerhalb von Astra oder über einen
späteren Ausbau geregelt werden (siehe „Abrechnung und Shop“ in den Known Limitations).
