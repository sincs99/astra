import type { Product, ProductInput } from "../services/api";
import { t } from "../i18n";
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
  if (!v.name.trim()) return t("ainst.prod.errName");
  if (v.blueprintId === "") return t("ainst.prod.errBlueprint");
  const memory = int(v.memory, 1);
  const disk = int(v.disk, 1);
  const cpu = int(v.cpu, 1);
  const swap = int(v.swap, 0);
  const io = int(v.io, 10, 1000);
  if (memory === null) return t("ainst.prod.errMemory");
  if (disk === null) return t("ainst.prod.errDisk");
  if (cpu === null) return t("ainst.prod.errCpu");
  if (swap === null) return t("ainst.prod.errSwap");
  if (io === null) return t("ainst.prod.errIo");
  const priceCents = parseEuroToCents(v.price);
  if (priceCents === null) return t("ainst.prod.errPrice");
  const currency = v.currency.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(currency)) return t("ainst.prod.errCurrency");
  const days = int(v.billingPeriodDays, 1, 3650);
  if (days === null) return t("ainst.prod.errDays");
  let max: number | null = null;
  if (v.maxInstancesPerUser.trim() !== "") {
    max = int(v.maxInstancesPerUser, 1);
    if (max === null) return t("ainst.prod.errMax");
  }
  // Gratis-Produkte brauchen ein Limit, sonst gaebe es unbegrenzt viele Gratis-Server (wie im Backend)
  if (priceCents === 0 && max === null) {
    return t("ainst.prod.errFree");
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
