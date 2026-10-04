/** Clientseitige Aggregation fuer die Admin-Uebersicht (aus GET /admin/orders und /admin/agents/monitoring). */
import type { AgentMonitoringEntry, Order, OrderStatus, PaymentEvent } from "../services/api";
import { parseUtc } from "./dates";

const DAY_MS = 86_400_000;

export interface RevenueSummary {
  /** Umsatz je Waehrung in Cent */
  byCurrency: Record<string, number>;
  /** Anzahl bezahlter, kostenpflichtiger Bestellungen im Zeitraum */
  paidCount: number;
}

/**
 * Umsatz der letzten `days` Tage: Bestellungen mit `paid_at` im Zeitraum, Summe von `price_cents`
 * (erstattete Bestellungen zaehlen nicht).
 * Naeherung: `paid_at` zeigt nur die letzte Zahlung einer Bestellung, fruehere Verlaengerungen fehlen.
 */
export function revenueLastDays(orders: Order[], days = 30, now: number = Date.now()): RevenueSummary {
  const byCurrency: Record<string, number> = {};
  let paidCount = 0;
  for (const o of orders) {
    if (!o.paid_at || o.price_cents <= 0 || o.status === "refunded") continue;
    const t = parseUtc(o.paid_at).getTime();
    if (Number.isNaN(t) || t > now || now - t > days * DAY_MS) continue;
    byCurrency[o.currency] = (byCurrency[o.currency] ?? 0) + o.price_cents;
    paidCount += 1;
  }
  return { byCurrency, paidCount };
}

export const OVERVIEW_STATUSES: OrderStatus[] = ["pending_payment", "awaiting_provisioning", "active", "past_due"];

export function countByStatus(orders: Order[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const s of OVERVIEW_STATUSES) out[s] = 0;
  for (const o of orders) if (o.status in out) out[o.status] += 1;
  return out;
}

export interface FleetLoad {
  /** Agents mit hinterlegter Kapazitaet fuer die jeweilige Ressource */
  memory: { used: number; total: number; percent: number };
  disk: { used: number; total: number; percent: number };
  cpu: { used: number; total: number; percent: number };
  agentCount: number;
  /** Aktive Agents ohne hinterlegte Kapazitaet (kein Limit): sie fliessen nicht in die Prozente ein */
  withoutLimit: number;
  /** Agent mit der hoechsten Speicher-/Disk-/CPU-Auslastung */
  busiest: { name: string; percent: number } | null;
}

const pct = (used: number, total: number) => (total > 0 ? Math.round((used / total) * 100) : 0);

/** Summiert effektive Kapazitaet (inkl. Ueberallokation) und Belegung aktiver Agents. */
export function fleetLoad(agents: AgentMonitoringEntry[]): FleetLoad {
  const active = agents.filter((a) => a.is_active);
  const acc = { memory: { used: 0, total: 0 }, disk: { used: 0, total: 0 }, cpu: { used: 0, total: 0 } };
  let withoutLimit = 0;
  let busiest: FleetLoad["busiest"] = null;
  for (const a of active) {
    const c = a.capacity;
    const u = a.utilization;
    const hasLimit = c.effective_memory_mb > 0 || c.effective_disk_mb > 0 || c.effective_cpu_percent > 0;
    if (!hasLimit) { withoutLimit += 1; continue; }
    if (c.effective_memory_mb > 0) { acc.memory.used += u.used_memory_mb; acc.memory.total += c.effective_memory_mb; }
    if (c.effective_disk_mb > 0) { acc.disk.used += u.used_disk_mb; acc.disk.total += c.effective_disk_mb; }
    if (c.effective_cpu_percent > 0) { acc.cpu.used += u.used_cpu_percent; acc.cpu.total += c.effective_cpu_percent; }
    const top = Math.max(u.memory_utilization, u.disk_utilization, u.cpu_utilization);
    if (!busiest || top > busiest.percent) busiest = { name: a.name, percent: Math.round(top) };
  }
  return {
    memory: { ...acc.memory, percent: pct(acc.memory.used, acc.memory.total) },
    disk: { ...acc.disk, percent: pct(acc.disk.used, acc.disk.total) },
    cpu: { ...acc.cpu, percent: pct(acc.cpu.used, acc.cpu.total) },
    agentCount: active.length,
    withoutLimit,
    busiest,
  };
}

/** Zusammenfuehren mehrerer Ereignislisten: neueste zuerst, ohne Duplikate. */
export function mergeEvents(...lists: PaymentEvent[][]): PaymentEvent[] {
  const seen = new Set<number>();
  const all: PaymentEvent[] = [];
  for (const l of lists) for (const e of l) if (!seen.has(e.id)) { seen.add(e.id); all.push(e); }
  return all.sort((a, b) => (b.received_at ?? "").localeCompare(a.received_at ?? "") || b.id - a.id);
}
