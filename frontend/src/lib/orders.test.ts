import { describe, expect, it } from "vitest";
import { hasRunningOrder, ORDER_END_NOTICE } from "./orders";
import { makeOrder } from "../test/fixtures";

describe("hasRunningOrder", () => {
  const orders = [
    makeOrder({ uuid: "a", status: "active", instance_uuid: "inst-1" }),
    makeOrder({ uuid: "b", status: "past_due", instance_uuid: "inst-2" }),
    makeOrder({ uuid: "c", status: "expired", instance_uuid: "inst-3" }),
    makeOrder({ uuid: "d", status: "pending_payment", instance_uuid: null }),
  ];

  it("erkennt aktive und ueberfaellige Bestellungen der Instance", () => {
    expect(hasRunningOrder(orders, "inst-1")).toBe(true);
    expect(hasRunningOrder(orders, "inst-2")).toBe(true);
  });

  it("ignoriert beendete Bestellungen, fremde Instances und fehlende UUID", () => {
    expect(hasRunningOrder(orders, "inst-3")).toBe(false);
    expect(hasRunningOrder(orders, "unbekannt")).toBe(false);
    expect(hasRunningOrder(orders, undefined)).toBe(false);
    expect(hasRunningOrder([], "inst-1")).toBe(false);
  });

  it("nennt den Hinweis ohne Erstattung", () => {
    expect(ORDER_END_NOTICE).toBe("Die laufende Bestellung endet damit, eine Erstattung erfolgt nicht.");
  });
});
