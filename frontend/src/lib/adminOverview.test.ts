import { describe, expect, it } from "vitest";
import { countByStatus, fleetLoad, mergeEvents, revenueLastDays } from "./adminOverview";
import type { AgentMonitoringEntry, PaymentEvent } from "../services/api";
import { makeOrder } from "../test/fixtures";

const NOW = Date.parse("2026-10-04T12:00:00Z");

describe("revenueLastDays", () => {
  it("summiert nur bezahlte Bestellungen der letzten 30 Tage je Waehrung", () => {
    const orders = [
      makeOrder({ price_cents: 999, paid_at: "2026-10-01T10:00:00" }),
      makeOrder({ price_cents: 500, paid_at: "2026-09-10T10:00:00Z" }),
      makeOrder({ price_cents: 700, currency: "CHF", paid_at: "2026-10-03T10:00:00Z" }),
      makeOrder({ price_cents: 1000, paid_at: "2026-08-01T10:00:00Z" }), // zu alt
      makeOrder({ price_cents: 0, paid_at: "2026-10-02T10:00:00Z" }), // kostenlos
      makeOrder({ price_cents: 800, paid_at: null }), // unbezahlt
    ];
    expect(revenueLastDays(orders, 30, NOW)).toEqual({ byCurrency: { EUR: 1499, CHF: 700 }, paidCount: 3 });
  });
});

describe("countByStatus", () => {
  it("zaehlt die vier relevanten Status und ignoriert andere", () => {
    const orders = [
      makeOrder({ status: "active" }), makeOrder({ status: "active" }),
      makeOrder({ status: "past_due" }), makeOrder({ status: "cancelled" }),
    ];
    expect(countByStatus(orders)).toEqual({ pending_payment: 0, awaiting_provisioning: 0, active: 2, past_due: 1 });
  });
});

function agent(over: Partial<AgentMonitoringEntry> & { mem?: [number, number]; disk?: [number, number]; cpu?: [number, number] }): AgentMonitoringEntry {
  const [mu, mt] = over.mem ?? [0, 0];
  const [du, dt] = over.disk ?? [0, 0];
  const [cu, ct] = over.cpu ?? [0, 0];
  return {
    id: 1, name: "n1", fqdn: "n1", health_status: "healthy", is_active: true, is_stale: false, last_seen_at: null,
    maintenance_mode: false, maintenance_reason: null, maintenance_started_at: null, available_for_deployment: true,
    capacity: {
      memory_total_mb: mt, disk_total_mb: dt, cpu_total_percent: ct, memory_overalloc_percent: 0, disk_overalloc_percent: 0, cpu_overalloc_percent: 0,
      effective_memory_mb: mt, effective_disk_mb: dt, effective_cpu_percent: ct,
    },
    utilization: {
      instance_count: 1, used_memory_mb: mu, used_disk_mb: du, used_cpu_percent: cu,
      memory_utilization: mt ? (mu / mt) * 100 : 0, disk_utilization: dt ? (du / dt) * 100 : 0, cpu_utilization: ct ? (cu / ct) * 100 : 0,
    },
    instance_count: 1, endpoint_summary: { total: 0, assigned: 0, free: 0, locked: 0 },
    ...over,
  } as AgentMonitoringEntry;
}

describe("fleetLoad", () => {
  it("summiert effektive Kapazitaet, ueberspringt inaktive und Agents ohne Limit", () => {
    const load = fleetLoad([
      agent({ id: 1, name: "a", mem: [2048, 4096], disk: [1000, 10000], cpu: [100, 400] }),
      agent({ id: 2, name: "b", mem: [3072, 4096], disk: [0, 10000], cpu: [200, 400] }),
      agent({ id: 3, name: "ohne" }),
      agent({ id: 4, name: "aus", is_active: false, mem: [1, 1] }),
    ]);
    expect(load.memory).toEqual({ used: 5120, total: 8192, percent: 63 });
    expect(load.disk).toEqual({ used: 1000, total: 20000, percent: 5 });
    expect(load.cpu).toEqual({ used: 300, total: 800, percent: 38 });
    expect(load.agentCount).toBe(3);
    expect(load.withoutLimit).toBe(1);
    expect(load.busiest).toEqual({ name: "b", percent: 75 });
  });

  it("liefert 0 Prozent und keinen Spitzenreiter ohne Agents", () => {
    const load = fleetLoad([]);
    expect(load.memory.percent).toBe(0);
    expect(load.busiest).toBeNull();
  });
});

describe("mergeEvents", () => {
  const ev = (id: number, received_at: string): PaymentEvent => ({
    id, event_id: `e${id}`, provider: "stripe", event_type: "x", order_uuid: null, status: "mismatch",
    detail: null, received_at, processed_at: null,
  });
  it("sortiert neueste zuerst und entfernt Duplikate", () => {
    const merged = mergeEvents([ev(1, "2026-10-01T00:00:00Z"), ev(2, "2026-10-03T00:00:00Z")], [ev(2, "2026-10-03T00:00:00Z"), ev(3, "2026-10-02T00:00:00Z")]);
    expect(merged.map((e) => e.id)).toEqual([2, 3, 1]);
  });
});
