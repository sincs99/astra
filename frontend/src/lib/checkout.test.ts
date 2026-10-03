import { describe, expect, it } from "vitest";
import { isManualPayment, readPaymentReturn, safeCheckoutUrl } from "./checkout";
import { ApiError } from "../services/api";

describe("isManualPayment", () => {
  it("erkennt 409 mit Code 'manual' oder Text 'manual'", () => {
    expect(isManualPayment(new ApiError("Zahlungsanbieter nicht konfiguriert", 409, "manual"))).toBe(true);
    expect(isManualPayment(new ApiError("Payment mode is manual", 409))).toBe(true);
  });
  it("ignoriert andere Fehler", () => {
    expect(isManualPayment(new ApiError("manual", 400))).toBe(false);
    expect(isManualPayment(new ApiError("Bestellung nicht offen", 409))).toBe(false);
    expect(isManualPayment(new Error("manual"))).toBe(false);
    expect(isManualPayment(null)).toBe(false);
  });
});

describe("safeCheckoutUrl", () => {
  it("erlaubt https", () => {
    expect(safeCheckoutUrl("https://checkout.stripe.com/c/pay/cs_test_123")).toBe("https://checkout.stripe.com/c/pay/cs_test_123");
  });
  it.each(["http://checkout.stripe.com/x", "javascript:alert(1)", "data:text/html,x", "//evil.example", "/orders", "", null, undefined, 42])(
    "lehnt %j ab", (value) => { expect(safeCheckoutUrl(value)).toBeNull(); });
});

describe("readPaymentReturn", () => {
  it("liest paid und cancelled", () => {
    expect(readPaymentReturn(new URLSearchParams("paid=abc"))).toEqual({ kind: "paid", orderUuid: "abc" });
    expect(readPaymentReturn(new URLSearchParams("cancelled=xyz"))).toEqual({ kind: "cancelled", orderUuid: "xyz" });
    expect(readPaymentReturn(new URLSearchParams(""))).toBeNull();
  });
});
