import { useEffect, useState } from "react";
import { api, type Blueprint, type Product } from "../services/api";
import { EMPTY_PRODUCT_FORM, productToForm, toProductPayload, type ProductFormValues } from "../lib/productForm";
import { formatPrice } from "../lib/money";
import {
  PageLayout, StatusBadge, LoadingState, EmptyState, ErrorState, ConfirmButton, Toast, useToast,
  cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, thStyle, tdStyle,
} from "../components/ui";

export function AdminProductsPage() {
  const toast = useToast();
  const [products, setProducts] = useState<Product[]>([]);
  const [blueprints, setBlueprints] = useState<Blueprint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<ProductFormValues>(EMPTY_PRODUCT_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [p, b] = await Promise.all([api.getAdminProducts(), api.getBlueprints()]);
      setProducts(p);
      setBlueprints(b);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const set = <K extends keyof ProductFormValues>(key: K, value: ProductFormValues[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const reset = () => { setForm(EMPTY_PRODUCT_FORM); setEditingId(null); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = toProductPayload(form);
    if (typeof payload === "string") { toast.error(payload); return; }
    try {
      setSubmitting(true);
      if (editingId === null) {
        await api.createProduct(payload);
        toast.success(`Produkt "${payload.name}" erstellt.`);
      } else {
        await api.updateProduct(editingId, payload);
        toast.success(`Produkt "${payload.name}" gespeichert.`);
      }
      reset();
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleActive = async (p: Product) => {
    try {
      await api.updateProduct(p.id, { is_active: !p.is_active });
      toast.success(p.is_active ? `"${p.name}" deaktiviert.` : `"${p.name}" aktiviert.`);
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Aktion fehlgeschlagen");
    }
  };

  const remove = async (p: Product) => {
    try {
      await api.deleteProduct(p.id);
      if (editingId === p.id) reset();
      toast.success(`Produkt "${p.name}" gelöscht.`);
      await load();
    } catch (err) {
      // z.B. 409, wenn noch Bestellungen existieren: Text des Backends zeigen
      toast.error(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
    }
  };

  const numberField = (id: string, label: string, key: keyof ProductFormValues, min: number, max?: number) => (
    <div>
      <label htmlFor={`prod-${id}`} style={labelStyle}>{label}</label>
      <input id={`prod-${id}`} type="number" min={min} max={max} value={form[key] as string}
        onChange={(e) => set(key, e.target.value as never)} style={inputStyle} />
    </div>
  );

  return (
    <PageLayout title="Produkte">
      <Toast {...toast} />

      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>
          {editingId === null ? "Neues Produkt" : "Produkt bearbeiten"}
        </h2>
        <form onSubmit={submit} noValidate>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
            <div>
              <label htmlFor="prod-name" style={labelStyle}>Name *</label>
              <input id="prod-name" type="text" value={form.name} onChange={(e) => set("name", e.target.value)}
                placeholder="z.B. Minecraft Starter" style={inputStyle} />
            </div>
            <div>
              <label htmlFor="prod-blueprint" style={labelStyle}>Blueprint *</label>
              <select id="prod-blueprint" value={form.blueprintId}
                onChange={(e) => set("blueprintId", e.target.value ? Number(e.target.value) : "")} style={inputStyle}>
                <option value="">– Wählen –</option>
                {blueprints.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="prod-price" style={labelStyle}>Preis (€) *</label>
              <input id="prod-price" type="text" inputMode="decimal" value={form.price}
                onChange={(e) => set("price", e.target.value)} placeholder="9,99" style={inputStyle} />
            </div>
            <div>
              <label htmlFor="prod-currency" style={labelStyle}>Währung</label>
              <input id="prod-currency" type="text" maxLength={3} value={form.currency}
                onChange={(e) => set("currency", e.target.value)} style={inputStyle} />
            </div>
            {numberField("days", "Laufzeit (Tage)", "billingPeriodDays", 1, 3650)}
            {numberField("max", "Max. Instances pro Nutzer (leer = unbegrenzt, bei Gratis Pflicht)", "maxInstancesPerUser", 1)}
          </div>

          <div style={{ marginTop: 12 }}>
            <label htmlFor="prod-desc" style={labelStyle}>Beschreibung</label>
            <textarea id="prod-desc" rows={2} value={form.description}
              onChange={(e) => set("description", e.target.value)} style={{ ...inputStyle, resize: "vertical" }} />
          </div>

          <fieldset style={{ border: "1px solid #e0e0e0", borderRadius: 6, marginTop: 12, padding: "8px 12px" }}>
            <legend style={{ fontSize: 13, fontWeight: 600, color: "#555", padding: "0 4px" }}>Ressourcen der Instance</legend>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12 }}>
              {numberField("memory", "Memory (MB)", "memory", 1)}
              {numberField("disk", "Disk (MB)", "disk", 1)}
              {numberField("cpu", "CPU (%)", "cpu", 1)}
              {numberField("swap", "Swap (MB)", "swap", 0)}
              {numberField("io", "IO", "io", 10, 1000)}
            </div>
          </fieldset>

          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginTop: 12 }}>
            <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={form.active} onChange={(e) => set("active", e.target.checked)} />
              Aktiv (im Shop sichtbar)
            </label>
            <button type="submit" disabled={submitting} style={{ ...btnPrimary, opacity: submitting ? 0.6 : 1 }}>
              {submitting ? "…" : editingId === null ? "Produkt erstellen" : "Speichern"}
            </button>
            {editingId !== null && <button type="button" onClick={reset} style={btnDefault}>Abbrechen</button>}
          </div>
        </form>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {loading ? (
        <LoadingState message="Produkte werden geladen..." />
      ) : products.length === 0 ? (
        <EmptyState icon="🛒" message="Noch keine Produkte vorhanden." />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid #e0e0e0" }}>
            <caption style={{ position: "absolute", left: -9999 }}>Produkte</caption>
            <thead>
              <tr style={{ backgroundColor: "#f5f5f5" }}>
                <th scope="col" style={thStyle}>Name</th>
                <th scope="col" style={thStyle}>Blueprint</th>
                <th scope="col" style={thStyle}>Ressourcen</th>
                <th scope="col" style={thStyle}>Preis</th>
                <th scope="col" style={thStyle}>Status</th>
                <th scope="col" style={thStyle}>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id}>
                  <td style={tdStyle}>
                    <strong>{p.name}</strong>
                    {p.description && <div style={{ fontSize: 12, color: "#666" }}>{p.description}</div>}
                  </td>
                  <td style={tdStyle}>{blueprints.find((b) => b.id === p.blueprint_id)?.name ?? `#${p.blueprint_id}`}</td>
                  <td style={{ ...tdStyle, fontSize: 12 }}>{p.resources.memory} MB RAM · {p.resources.disk} MB Disk · {p.resources.cpu}% CPU</td>
                  <td style={tdStyle}>{formatPrice(p.price_cents, p.currency, p.billing_period_days)}</td>
                  <td style={tdStyle}>
                    <StatusBadge status={p.is_active ? "active" : "inactive"} size="sm" />
                  </td>
                  <td style={tdStyle}>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      <button type="button" style={{ ...btnDefault, padding: "4px 10px", fontSize: 12 }}
                        onClick={() => { setEditingId(p.id); setForm(productToForm(p)); window.scrollTo?.({ top: 0 }); }}>
                        ✏️ Bearbeiten
                      </button>
                      <button type="button" style={{ ...btnDefault, padding: "4px 10px", fontSize: 12 }} onClick={() => toggleActive(p)}>
                        {p.is_active ? "Deaktivieren" : "Aktivieren"}
                      </button>
                      <ConfirmButton label="Löschen" danger size="sm"
                        confirmMessage={`Produkt "${p.name}" wirklich löschen?`} onConfirm={() => remove(p)} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageLayout>
  );
}
