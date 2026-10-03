import { describe, expect, it } from "vitest";
import { EMPTY_PRODUCT_FORM, productToForm, toProductPayload } from "./productForm";
import { makeProduct } from "../test/fixtures";

const valid = { ...EMPTY_PRODUCT_FORM, name: " Starter ", blueprintId: 4 as const, price: "9,99" };

describe("toProductPayload", () => {
  it("rechnet Euro in Cent um und uebernimmt Defaults", () => {
    expect(toProductPayload(valid)).toEqual({
      name: "Starter", description: null, blueprint_id: 4,
      memory: 1024, disk: 5120, cpu: 100, swap: 0, io: 500,
      price_cents: 999, currency: "EUR", billing_period_days: 30, is_active: true, max_instances_per_user: null,
    });
  });

  it("normalisiert die Waehrung und erlaubt kostenlose Produkte und Limits", () => {
    expect(toProductPayload({ ...valid, price: "0", currency: " eur ", maxInstancesPerUser: "2", description: " Text " }))
      .toMatchObject({ price_cents: 0, currency: "EUR", max_instances_per_user: 2, description: "Text" });
  });

  it("verlangt bei kostenlosen Produkten ein Limit pro Nutzer (wie das Backend)", () => {
    expect(toProductPayload({ ...valid, price: "0" })).toMatch(/Kostenlose Produkte/);
    expect(toProductPayload({ ...valid, price: "0,00", maxInstancesPerUser: "1" })).toMatchObject({ price_cents: 0, max_instances_per_user: 1 });
  });

  it("begrenzt die Laufzeit auf 1 bis 3650 Tage", () => {
    expect(toProductPayload({ ...valid, billingPeriodDays: "3651" })).toMatch(/Laufzeit/);
    expect(toProductPayload({ ...valid, billingPeriodDays: "3650" })).toMatchObject({ billing_period_days: 3650 });
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
    const form = productToForm(makeProduct({
      description: null, price_cents: 1250, is_active: false, max_instances_per_user: null,
      resources: { memory: 4096, swap: 512, disk: 20480, io: 300, cpu: 200 },
    }));
    expect(form).toMatchObject({
      price: "12,50", maxInstancesPerUser: "", active: false, blueprintId: 1, description: "",
      memory: "4096", swap: "512", disk: "20480", io: "300", cpu: "200",
    });
    expect(toProductPayload(form)).toMatchObject({ price_cents: 1250, is_active: false, memory: 4096, swap: 512 });
  });
});
