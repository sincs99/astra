import { useEffect, useState } from "react";
import { api, type Blueprint, type Product } from "../services/api";
import { EMPTY_PRODUCT_FORM, productToForm, toProductPayload, type ProductFormValues } from "../lib/productForm";
import { formatPrice } from "../lib/money";
import { t } from "../i18n";
import { PageLayout, StatusBadge, ConfirmButton, Toast, useToast, ScrollRegion } from "../components/ui";
import { Icon } from "../components/ui/Icon";
import { Field, ErrorBanner, fieldGrid } from "../components/admin/AdminField";

export function AdminProductsPage() {
  const toast = useToast();
  const [products, setProducts] = useState<Product[]>([]);
  const [blueprints, setBlueprints] = useState<Blueprint[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState<ProductFormValues>(EMPTY_PRODUCT_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      setLoadError(null);
      const [p, b] = await Promise.all([api.getAdminProducts(), api.getBlueprints()]);
      setProducts(p);
      setBlueprints(b);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : t("ainst.prod.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const set = <K extends keyof ProductFormValues>(key: K, value: ProductFormValues[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const reset = () => { setForm(EMPTY_PRODUCT_FORM); setEditingId(null); setFormError(null); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = toProductPayload(form);
    if (typeof payload === "string") { setFormError(payload); return; }
    try {
      setSubmitting(true);
      setFormError(null);
      if (editingId === null) {
        await api.createProduct(payload);
        toast.success(t("ainst.prod.created", { name: payload.name }));
      } else {
        await api.updateProduct(editingId, payload);
        toast.success(t("ainst.prod.saved", { name: payload.name }));
      }
      reset();
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : t("ainst.prod.saveFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const toggleActive = async (p: Product) => {
    try {
      await api.updateProduct(p.id, { is_active: !p.is_active });
      toast.success(t(p.is_active ? "ainst.prod.deactivated" : "ainst.prod.activated", { name: p.name }));
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("ainst.prod.actionFailed"));
    }
  };

  const remove = async (p: Product) => {
    try {
      await api.deleteProduct(p.id);
      if (editingId === p.id) reset();
      toast.success(t("ainst.prod.deleted", { name: p.name }));
      await load();
    } catch (err) {
      // z.B. 409, wenn noch Bestellungen existieren: Text des Backends zeigen
      toast.error(err instanceof Error ? err.message : t("ainst.prod.deleteFailed"));
    }
  };

  const numberField = (label: string, key: keyof ProductFormValues, min: number, max?: number) => (
    <Field label={label}>
      <input className="inp mono" type="number" min={min} max={max} value={form[key] as string}
        onChange={(e) => set(key, e.target.value as never)} />
    </Field>
  );

  const col = {
    name: t("ainst.prod.colName"), blueprint: t("ainst.prod.colBlueprint"), resources: t("ainst.prod.colResources"),
    price: t("ainst.prod.colPrice"), status: t("ainst.prod.colStatus"), actions: t("ainst.prod.colActions"),
  };

  return (
    <PageLayout title={t("ainst.prod.title")}>
      <Toast {...toast} />
      <div className="stack">

        <section className="panel" aria-labelledby="prod-form-title">
          <div className="panel-head">
            <h2 id="prod-form-title">{editingId === null ? t("ainst.prod.newTitle") : t("ainst.prod.editTitle")}</h2>
          </div>
          <form className="panel-body" onSubmit={submit} noValidate>
            <p className="hint">{t("ainst.required")}</p>
            {formError && <ErrorBanner message={formError} />}
            <div style={fieldGrid(200)}>
              <Field label={t("ainst.prod.name")}>
                <input className="inp" type="text" value={form.name} onChange={(e) => set("name", e.target.value)}
                  placeholder={t("ainst.prod.namePh")} aria-required="true" />
              </Field>
              <Field label={t("ainst.prod.blueprint")}>
                <select className="inp" value={form.blueprintId} aria-required="true"
                  onChange={(e) => set("blueprintId", e.target.value ? Number(e.target.value) : "")}>
                  <option value="">{t("ainst.choose")}</option>
                  {blueprints.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select>
              </Field>
              <Field label={t("ainst.prod.price")}>
                <input className="inp mono" type="text" inputMode="decimal" value={form.price}
                  onChange={(e) => set("price", e.target.value)} placeholder={t("ainst.prod.pricePh")} aria-required="true" />
              </Field>
              <Field label={t("ainst.prod.currency")}>
                <input className="inp mono" type="text" maxLength={3} value={form.currency}
                  onChange={(e) => set("currency", e.target.value)} />
              </Field>
              {numberField(t("ainst.prod.days"), "billingPeriodDays", 1, 3650)}
              {numberField(t("ainst.prod.max"), "maxInstancesPerUser", 1)}
            </div>

            <Field label={t("ainst.prod.description")}>
              <textarea className="inp" rows={2} value={form.description}
                onChange={(e) => set("description", e.target.value)} style={{ resize: "vertical", padding: "8px 12px" }} />
            </Field>

            <fieldset className="fieldset">
              <legend className="panel-title">{t("ainst.prod.resources")}</legend>
              <div style={fieldGrid(130)}>
                {numberField(t("ainst.prod.memory"), "memory", 1)}
                {numberField(t("ainst.prod.disk"), "disk", 1)}
                {numberField(t("ainst.prod.cpu"), "cpu", 1)}
                {numberField(t("ainst.prod.swap"), "swap", 0)}
                {numberField(t("ainst.prod.io"), "io", 10, 1000)}
              </div>
            </fieldset>

            <div className="row-actions">
              <label style={{ display: "inline-flex", gap: 6, alignItems: "center", fontSize: "var(--fs-small)" }}>
                <input type="checkbox" checked={form.active} onChange={(e) => set("active", e.target.checked)} />
                {t("ainst.prod.active")}
              </label>
              <span className="push" style={{ display: "inline-flex", gap: 8 }}>
                {editingId !== null && <button type="button" className="btn" onClick={reset}>{t("ainst.prod.cancel")}</button>}
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? t("ainst.prod.saving") : editingId === null ? t("ainst.prod.create") : t("ainst.prod.save")}
                </button>
              </span>
            </div>
          </form>
        </section>

        <section className="panel" aria-labelledby="prod-list-title">
          <div className="panel-head"><h2 id="prod-list-title">{t("ainst.prod.listTitle")}</h2></div>
          {loadError && (
            <div className="panel-body">
              <ErrorBanner message={loadError} title={t("ainst.errorTitle")} retryLabel={t("ainst.retry")} onRetry={load} />
            </div>
          )}
          {loading ? (
            <div className="panel-body"><p className="hint" role="status" aria-busy="true">{t("ainst.prod.loading")}</p></div>
          ) : products.length === 0 ? (
            !loadError && <div className="panel-body"><p className="hint">{t("ainst.prod.empty")}</p></div>
          ) : (
            <ScrollRegion label={t("ainst.prod.tableLabel")}>
              <table className="tbl tbl-cards">
                <caption className="sr-only">{t("ainst.prod.title")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{col.name}</th>
                    <th scope="col">{col.blueprint}</th>
                    <th scope="col">{col.resources}</th>
                    <th scope="col">{col.price}</th>
                    <th scope="col">{col.status}</th>
                    <th scope="col">{col.actions}</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <tr key={p.id}>
                      <td data-label={col.name}>
                        <strong>{p.name}</strong>
                        {p.description && <div className="hint">{p.description}</div>}
                      </td>
                      <td data-label={col.blueprint}>{blueprints.find((b) => b.id === p.blueprint_id)?.name ?? `#${p.blueprint_id}`}</td>
                      <td data-label={col.resources}>
                        <span className="mono">{t("ainst.prod.resFmt", { memory: p.resources.memory, disk: p.resources.disk, cpu: p.resources.cpu })}</span>
                      </td>
                      <td data-label={col.price}><span className="mono">{formatPrice(p.price_cents, p.currency, p.billing_period_days)}</span></td>
                      <td data-label={col.status}><StatusBadge status={p.is_active ? "active" : "inactive"} size="sm" /></td>
                      <td data-label={col.actions}>
                        <div className="row-actions" style={{ marginTop: 0 }}>
                          <button type="button" className="btn btn-sm"
                            onClick={() => { setEditingId(p.id); setForm(productToForm(p)); setFormError(null); window.scrollTo?.({ top: 0 }); }}>
                            <Icon name="pencil" size={14} />{t("ainst.prod.edit")}
                          </button>
                          <button type="button" className="btn btn-sm" onClick={() => toggleActive(p)}>
                            {p.is_active ? t("ainst.prod.deactivate") : t("ainst.prod.activate")}
                          </button>
                          <ConfirmButton label={t("ainst.prod.delete")} danger size="sm"
                            confirmMessage={t("ainst.prod.confirmDelete", { name: p.name })} onConfirm={() => remove(p)} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          )}
        </section>
      </div>
    </PageLayout>
  );
}
