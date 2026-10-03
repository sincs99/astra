import type { Order, Product } from "../services/api";

/** Produkt in der Form, wie das Backend es liefert (Admin-Sicht). */
export function makeProduct(patch: Partial<Product> = {}): Product {
  return {
    id: 5, name: "Starter", description: "Für kleine Server",
    price_cents: 999, currency: "EUR", billing_period_days: 30,
    resources: { memory: 2048, swap: 0, disk: 10240, io: 500, cpu: 150 },
    blueprint_id: 1, is_active: true, max_instances_per_user: null,
    created_at: null, updated_at: null,
    ...patch,
  };
}

/** Bestellung in der Form, wie das Backend sie liefert. */
export function makeOrder(patch: Partial<Order> = {}): Order {
  return {
    id: 1, uuid: "order-uuid-1", status: "pending_payment",
    product_id: 5, product_name: "Starter", instance_name: "Mein Server",
    instance_uuid: null, instance_status: null, connection: null,
    price_cents: 999, currency: "EUR", billing_period_days: 30,
    resources: { memory: 2048, swap: 0, disk: 10240, io: 500, cpu: 150 },
    payment_reference: null, paid_at: null, current_period_end: null,
    cancel_at_period_end: false, cancelled_at: null, created_at: null,
    ...patch,
  };
}
