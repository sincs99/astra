import { ApiError } from "../services/api";

/**
 * Das Backend antwortet auf den Checkout-Aufruf mit 409 "manual", solange kein Zahlungsanbieter
 * konfiguriert ist (Zahlung ausserhalb von Astra, Admin bestaetigt). Erkannt wird sowohl ein Fehlercode
 * "manual" als auch ein Fehlertext, der "manual" enthaelt.
 */
export function isManualPayment(err: unknown): boolean {
  return err instanceof ApiError && err.status === 409 && (err.code === "manual" || /\bmanual\b/i.test(err.message));
}

/** Nur https-Ziele (Stripe Checkout) sind erlaubt; alles andere wird nicht aufgerufen. */
export function safeCheckoutUrl(url: unknown): string | null {
  if (typeof url !== "string") return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

export type PaymentReturn = { kind: "paid" | "cancelled"; orderUuid: string } | null;

/** Liest die Rueckkehr von Stripe: /orders?paid=<uuid> oder ?cancelled=<uuid>. */
export function readPaymentReturn(params: URLSearchParams): PaymentReturn {
  const paid = params.get("paid");
  if (paid) return { kind: "paid", orderUuid: paid };
  const cancelled = params.get("cancelled");
  if (cancelled) return { kind: "cancelled", orderUuid: cancelled };
  return null;
}
