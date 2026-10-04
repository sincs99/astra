import { useState } from "react";
import { api, ApiError, type Order } from "../services/api";
import { isManualPayment, safeCheckoutUrl } from "../lib/checkout";
import { t } from "../i18n";

/**
 * Online-Zahlung starten (Stripe): holt die Checkout-Adresse und leitet weiter.
 * Liefert "manual", wenn nur per Überweisung bezahlt wird, und "stale", wenn sich der Status der Bestellung geändert hat.
 */
export function useCheckout(onError: (message: string) => void) {
  const [paying, setPaying] = useState<string | null>(null);

  const pay = async (order: Pick<Order, "uuid">): Promise<"redirected" | "manual" | "stale" | "failed"> => {
    try {
      setPaying(order.uuid);
      const { checkout_url } = await api.createCheckout(order.uuid);
      const target = safeCheckoutUrl(checkout_url);
      if (!target) {
        onError(t("orders.badCheckout"));
        return "failed";
      }
      window.location.assign(target);
      return "redirected";
    } catch (err) {
      if (isManualPayment(err)) return "manual";
      onError(err instanceof Error ? err.message : t("orders.payFailed"));
      return err instanceof ApiError && err.code === "invalid_status" ? "stale" : "failed";
    } finally {
      setPaying(null);
    }
  };

  return { pay, paying };
}
