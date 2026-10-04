/** Reine Hilfen für das Kunden-Dashboard (Serverkarten, Laufzeit, offene Bestellungen). */
import type { Instance, Order } from "../services/api";
import { parseUtc } from "./dates";

const DAY_MS = 86_400_000;
/** Ab so vielen Tagen vor Laufzeitende wird "Verlängern" hervorgehoben. */
export const RENEW_SOON_DAYS = 7;

/** Status für das Badge: bei bereiter Instance zählt der Container-Zustand (läuft/gestoppt). */
export function instanceState(inst: Pick<Instance, "status" | "container_state">): string {
  const status = inst.status ?? "ready";
  if (status !== "ready") return status;
  switch (inst.container_state) {
    case "running": return "running";
    case "starting": return "starting";
    case "stopping": return "stopping";
    case "offline":
    case "stopped": return "stopped";
    default: return "ready";
  }
}

export function isRunning(inst: Pick<Instance, "status" | "container_state">): boolean {
  return instanceState(inst) === "running";
}

/** Bestellung, die zu einer Instance gehört (über instance_uuid). */
export function orderForInstance(orders: Order[], instanceUuid: string): Order | undefined {
  return orders.find((o) => o.instance_uuid === instanceUuid);
}

export type Expiry =
  | { kind: "none" }
  | { kind: "ok"; date: string }
  | { kind: "soon"; date: string; days: number }
  | { kind: "overdue"; date: string };

/** Laufzeitende einer Bestellung: normal, bald fällig (<= 7 Tage) oder überfällig. */
export function expiryOf(order: Order | undefined, now: number = Date.now()): Expiry {
  if (!order || !order.current_period_end || (order.status !== "active" && order.status !== "past_due")) return { kind: "none" };
  const end = parseUtc(order.current_period_end).getTime();
  if (Number.isNaN(end)) return { kind: "none" };
  if (order.status === "past_due" || end < now) return { kind: "overdue", date: order.current_period_end };
  const days = Math.ceil((end - now) / DAY_MS);
  return days <= RENEW_SOON_DAYS
    ? { kind: "soon", date: order.current_period_end, days }
    : { kind: "ok", date: order.current_period_end };
}

/** "Verlängern" anbieten: kostenpflichtig, aktiv/überfällig und bald fällig oder überfällig. */
export function canRenew(order: Order | undefined, now: number = Date.now()): boolean {
  if (!order || order.price_cents <= 0) return false;
  const e = expiryOf(order, now);
  return e.kind === "soon" || e.kind === "overdue";
}

/** Bestellungen ohne Server, die auf Zahlung warten. */
export function pendingPayment(orders: Order[]): Order[] {
  return orders.filter((o) => o.status === "pending_payment" && !o.instance_uuid);
}

/** Bezahlte Bestellungen, deren Server noch eingerichtet wird (kein freier Node). */
export function waitingForCapacity(orders: Order[]): Order[] {
  return orders.filter((o) => o.status === "awaiting_provisioning" && !o.instance_uuid);
}

/** Anzeige von MB als "2 GB" bzw. "512 MB". */
export function formatMemory(mb: number, locale: string): string {
  if (mb >= 1024) return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(mb / 1024)} GB`;
  return `${mb} MB`;
}
