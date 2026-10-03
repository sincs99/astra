import type { Product, ProductInput } from "../services/api";
import { centsToEuroInput, parseEuroToCents } from "./money";

export interface ProductFormValues {
  name: string;
  description: string;
  blueprintId: number | "";
  memory: string;
  disk: string;
  cpu: string;
  swap: string;
  io: string;
  /** Euro mit bis zu 2 Dezimalstellen, z.B. "9,99" */
  price: string;
  currency: string;
  billingPeriodDays: string;
  active: boolean;
  /** Leer = unbegrenzt */
  maxInstancesPerUser: string;
}

export const EMPTY_PRODUCT_FORM: ProductFormValues = {
  name: "", description: "", blueprintId: "",
  memory: "1024", disk: "5120", cpu: "100", swap: "0", io: "500",
  price: "", currency: "EUR", billingPeriodDays: "30", active: true, maxInstancesPerUser: "",
};

export function productToForm(p: Product): ProductFormValues {
  return {
    name: p.name,
    description: p.description ?? "",
    blueprintId: p.blueprint_id ?? "",
    memory: String(p.resources.memory), disk: String(p.resources.disk), cpu: String(p.resources.cpu),
    swap: String(p.resources.swap), io: String(p.resources.io),
    price: centsToEuroInput(p.price_cents).replace(".", ","),
    currency: p.currency,
    billingPeriodDays: String(p.billing_period_days),
    active: p.is_active ?? true,
    maxInstancesPerUser: p.max_instances_per_user == null ? "" : String(p.max_instances_per_user),
  };
}

function int(value: string, min: number, max = Number.MAX_SAFE_INTEGER): number | null {
  if (!/^\d+$/.test(value.trim())) return null;
  const n = Number(value);
  return n >= min && n <= max ? n : null;
}

/** Liefert den API-Payload oder eine Fehlermeldung (string). */
export function toProductPayload(v: ProductFormValues): ProductInput | string {
  if (!v.name.trim()) return "Bitte einen Namen angeben.";
  if (v.blueprintId === "") return "Bitte einen Blueprint wählen.";
  const memory = int(v.memory, 1);
  const disk = int(v.disk, 1);
  const cpu = int(v.cpu, 1);
  const swap = int(v.swap, 0);
  const io = int(v.io, 10, 1000);
  if (memory === null) return "Memory (MB) muss eine ganze Zahl ≥ 1 sein.";
  if (disk === null) return "Disk (MB) muss eine ganze Zahl ≥ 1 sein.";
  if (cpu === null) return "CPU (%) muss eine ganze Zahl ≥ 1 sein.";
  if (swap === null) return "Swap (MB) muss eine ganze Zahl ≥ 0 sein.";
  if (io === null) return "IO muss zwischen 10 und 1000 liegen.";
  const priceCents = parseEuroToCents(v.price);
  if (priceCents === null) return "Der Preis muss ein Betrag in Euro mit höchstens 2 Dezimalstellen sein, z.B. 9,99.";
  const currency = v.currency.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(currency)) return "Die Währung muss ein 3-stelliger Code sein, z.B. EUR.";
  const days = int(v.billingPeriodDays, 1, 3650);
  if (days === null) return "Die Laufzeit muss zwischen 1 und 3650 Tagen liegen.";
  let max: number | null = null;
  if (v.maxInstancesPerUser.trim() !== "") {
    max = int(v.maxInstancesPerUser, 1);
    if (max === null) return "Max. Instances pro Nutzer muss leer (unbegrenzt) oder ≥ 1 sein.";
  }
  // Gratis-Produkte brauchen ein Limit, sonst gaebe es unbegrenzt viele Gratis-Server (wie im Backend)
  if (priceCents === 0 && max === null) {
    return "Kostenlose Produkte brauchen „Max. Instances pro Nutzer“ (sonst unbegrenzt viele Gratis-Server).";
  }
  return {
    name: v.name.trim(),
    description: v.description.trim() || null,
    blueprint_id: v.blueprintId,
    memory, disk, cpu, swap, io,
    price_cents: priceCents,
    currency,
    billing_period_days: days,
    is_active: v.active,
    max_instances_per_user: max,
  };
}
