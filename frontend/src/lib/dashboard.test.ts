import { describe, expect, it } from "vitest";
import { canRenew, expiryOf, formatMemory, instanceState, isRunning, orderForInstance, pendingPayment, waitingForCapacity } from "./dashboard";
import { makeOrder } from "../test/fixtures";

const NOW = Date.parse("2026-10-04T12:00:00Z");
const inDays = (d: number) => new Date(NOW + d * 86_400_000).toISOString();

describe("instanceState", () => {
  it("nutzt bei bereiter Instance den Container-Zustand", () => {
    expect(instanceState({ status: "ready", container_state: "running" })).toBe("running");
    expect(instanceState({ status: "ready", container_state: "offline" })).toBe("stopped");
    expect(instanceState({ status: "ready", container_state: null })).toBe("ready");
    expect(instanceState({ status: null, container_state: null })).toBe("ready");
  });
  it("zeigt andere Lebenszyklus-Status unveraendert", () => {
    expect(instanceState({ status: "suspended", container_state: "running" })).toBe("suspended");
    expect(isRunning({ status: "provisioning", container_state: "running" })).toBe(false);
    expect(isRunning({ status: "ready", container_state: "running" })).toBe(true);
  });
});

describe("expiryOf / canRenew", () => {
  it("unterscheidet normal, bald faellig und ueberfaellig", () => {
    expect(expiryOf(makeOrder({ status: "active", current_period_end: inDays(30) }), NOW).kind).toBe("ok");
    expect(expiryOf(makeOrder({ status: "active", current_period_end: inDays(3) }), NOW)).toMatchObject({ kind: "soon", days: 3 });
    expect(expiryOf(makeOrder({ status: "active", current_period_end: inDays(7) }), NOW).kind).toBe("soon");
    expect(expiryOf(makeOrder({ status: "active", current_period_end: inDays(8) }), NOW).kind).toBe("ok");
    expect(expiryOf(makeOrder({ status: "past_due", current_period_end: inDays(-2) }), NOW).kind).toBe("overdue");
    expect(expiryOf(makeOrder({ status: "active", current_period_end: inDays(-1) }), NOW).kind).toBe("overdue");
  });
  it("kennt kein Ende ohne Bestellung, Laufzeitende oder aktiven Status", () => {
    expect(expiryOf(undefined, NOW).kind).toBe("none");
    expect(expiryOf(makeOrder({ status: "active", current_period_end: null }), NOW).kind).toBe("none");
    expect(expiryOf(makeOrder({ status: "cancelled", current_period_end: inDays(2) }), NOW).kind).toBe("none");
  });
  it("bietet Verlaengern nur bei kostenpflichtigen, bald faelligen oder ueberfaelligen Bestellungen", () => {
    expect(canRenew(makeOrder({ status: "active", current_period_end: inDays(3) }), NOW)).toBe(true);
    expect(canRenew(makeOrder({ status: "active", current_period_end: inDays(30) }), NOW)).toBe(false);
    expect(canRenew(makeOrder({ status: "past_due", current_period_end: inDays(-1) }), NOW)).toBe(true);
    expect(canRenew(makeOrder({ status: "active", current_period_end: inDays(3), price_cents: 0 }), NOW)).toBe(false);
    expect(canRenew(undefined, NOW)).toBe(false);
  });
});

describe("Bestellungen", () => {
  const orders = [
    makeOrder({ uuid: "a", status: "pending_payment" }),
    makeOrder({ uuid: "b", status: "pending_payment", instance_uuid: "i1" }),
    makeOrder({ uuid: "c", status: "awaiting_provisioning" }),
    makeOrder({ uuid: "d", status: "active", instance_uuid: "i2" }),
  ];
  it("filtert wartende Bestellungen ohne Server", () => {
    expect(pendingPayment(orders).map((o) => o.uuid)).toEqual(["a"]);
    expect(waitingForCapacity(orders).map((o) => o.uuid)).toEqual(["c"]);
    expect(orderForInstance(orders, "i2")?.uuid).toBe("d");
    expect(orderForInstance(orders, "x")).toBeUndefined();
  });
  it("formatiert Speicher", () => {
    expect(formatMemory(512, "de-CH")).toBe("512 MB");
    expect(formatMemory(8192, "de-CH")).toBe("8 GB");
    expect(formatMemory(1536, "en-GB")).toBe("1.5 GB");
  });
});
