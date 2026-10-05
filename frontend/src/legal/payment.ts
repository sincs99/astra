import { getLang } from "../i18n";

/**
 * Texte zum Zahlungsweg. Der Betreiber passt sie hier an, z.B. mit Bankverbindung und Zahlungsreferenz.
 * Wird angezeigt, solange kein Zahlungsanbieter konfiguriert ist (Checkout antwortet mit 409 "manual").
 */
export const MANUAL_PAYMENT_NOTICE = "Zahlung per Überweisung, Freischaltung durch den Betreiber.";
export const MANUAL_PAYMENT_NOTICE_EN = "Payment by bank trassnsfer, activation by the operator.";

/** Hinweistext in der aktuellen Sprache (Betreiber passt beide Texte oben an). */
export function manualPaymentNotice(): string {
  return getLang() === "en" ? MANUAL_PAYMENT_NOTICE_EN : MANUAL_PAYMENT_NOTICE;
}
