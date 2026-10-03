import type { Order } from "../services/api";

export const ORDER_END_NOTICE = "Die laufende Bestellung endet damit, eine Erstattung erfolgt nicht.";

/** Gehört die Instance zu einer laufenden (aktiven oder ueberfaelligen) Bestellung? */
export function hasRunningOrder(orders: Order[], instanceUuid: string | undefined): boolean {
  if (!instanceUuid) return false;
  return orders.some((o) => o.instance_uuid === instanceUuid && (o.status === "active" || o.status === "past_due"));
}
