import { describe, expect, it } from "vitest";
import { EMPTY_PRODUCT_FORM, productToForm, toProductPayload } from "./productForm";
import type { Product } from "../services/api";

const valid = { ...EMPTY_PRODUCT_FORM, name: " Starter ", blueprintId: 4 as const, price: "9,99" };

describe("toProductPayload", () => {
  it("rechnet Euro in Cent um und uebernimmt Defaults", () => {
    expect(toProductPayload(valid)).toEqual({
      name: "Starter", description: null, blueprint_id: 4,
      memory: 1024, disk: 5120, cpu: 100, swap: 0, io: 500,
      price_cents: 999, currency: "EUR", billing_period_days: 30, active: true, max_instances_per_user: null,
    });
  });

  it("normalisiert die Waehrung und erlaubt kostenlose Produkte und Limits", () => {
    expect(toProductPayload({ ...valid, price: "0", currency: " eur ", maxInstancesPerUser: "2", description: " Text " }))
      .toMatchObject({ price_cents: 0, currency: "EUR", max_instances_per_user: 2, description: "Text" });
  });

  it.each([
    [{ name: " " }, /Namen/],
    [{ blueprintId: "" as const }, /Blueprint/],
    [{ memory: "0" }, /Memory/],
    [{ disk: "abc" }, /Disk/],
    [{ cpu: "-5" }, /CPU/],
    [{ swap: "1.5" }, /Swap/],
    [{ io: "5" }, /IO/],
    [{ io: "1001" }, /IO/],
    [{ price: "9,999" }, /Preis/],
    [{ price: "" }, /Preis/],
    [{ currency: "EURO" }, /Währung/],
    [{ billingPeriodDays: "0" }, /Laufzeit/],
    [{ maxInstancesPerUser: "0" }, /Max\. Instances/],
  ])("meldet ungueltige Eingabe %j", (patch, message) => {
    const result = toProductPayload({ ...valid, ...patch });
    expect(typeof result).toBe("string");
    expect(result as string).toMatch(message);
  });
});

describe("productToForm", () => {
  it("zeigt den Preis in Euro und leere Limits als unbegrenzt", () => {
    const form = productToForm({
      id: 1, name: "P", description: null, blueprint_id: 2, memory: 2048, disk: 10240, cpu: 200, swap: 0, io: 500,
      price_cents: 1250, currency: "EUR", billing_period_days: 30, active: false, max_instances_per_user: null,
    } as Product);
    expect(form).toMatchObject({ price: "12,50", maxInstancesPerUser: "", active: false, blueprintId: 2, description: "" });
    expect(toProductPayload(form)).toMatchObject({ price_cents: 1250 });
  });
});
