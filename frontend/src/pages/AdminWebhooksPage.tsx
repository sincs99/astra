import { useEffect, useState } from "react";
import { api, type WebhookEntry, type WebhookEventInfo } from "../services/api";
import { PageLayout, StatusBadge, ConfirmButton, Toast, useToast } from "../components/ui";
import { Icon } from "../components/ui/Icon";
import { t } from "../i18n";

export function AdminWebhooksPage() {
  const toast = useToast();
  const [webhooks, setWebhooks] = useState<WebhookEntry[]>([]);
  const [availableEvents, setAvailableEvents] = useState<WebhookEventInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Formular
  const [editId, setEditId] = useState<number | null>(null);
  const [endpointUrl, setEndpointUrl] = useState("");
  const [description, setDescription] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [secretToken, setSecretToken] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const loadAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [whData, evData] = await Promise.all([
        api.getWebhooks(),
        api.getWebhookEvents(),
      ]);
      setWebhooks(whData);
      setAvailableEvents(evData);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("asys.hooks.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const resetForm = () => {
    setEditId(null);
    setEndpointUrl("");
    setDescription("");
    setSelectedEvents([]);
    setSecretToken("");
    setIsActive(true);
  };

  const startEdit = (wh: WebhookEntry) => {
    setEditId(wh.id);
    setEndpointUrl(wh.endpoint_url);
    setDescription(wh.description || "");
    setSelectedEvents(wh.events || []);
    setSecretToken(wh.secret_token);
    setIsActive(wh.is_active);
  };

  const toggleEvent = (event: string) => {
    setSelectedEvents(prev =>
      prev.includes(event) ? prev.filter(e => e !== event) : [...prev, event]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!endpointUrl.trim() || selectedEvents.length === 0) {
      setError(t("asys.hooks.required"));
      return;
    }
    try {
      setSubmitting(true);
      setError(null);
      if (editId) {
        await api.updateWebhook(editId, {
          endpoint_url: endpointUrl.trim(),
          description: description.trim() || undefined,
          events: selectedEvents,
          secret_token: secretToken || undefined,
          is_active: isActive,
        });
        toast.success(t("asys.hooks.updated"));
      } else {
        await api.createWebhook({
          endpoint_url: endpointUrl.trim(),
          description: description.trim() || undefined,
          events: selectedEvents,
          secret_token: secretToken.trim() || undefined,
          is_active: isActive,
        });
        toast.success(t("asys.hooks.created"));
      }
      resetForm();
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("asys.hooks.saveFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      setError(null);
      await api.deleteWebhook(id);
      toast.success(t("asys.hooks.deleted"));
      if (editId === id) resetForm();
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("asys.hooks.deleteFailed"));
    }
  };

  const handleTest = async (id: number) => {
    try {
      const result = await api.testWebhook(id);
      if (result.success) {
        toast.success(t("asys.hooks.testOk", { message: result.message }));
      } else {
        toast.error(t("asys.hooks.testFail", { message: result.message }));
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("asys.hooks.testFailedError"));
    }
  };

  const handleToggleActive = async (wh: WebhookEntry) => {
    try {
      await api.updateWebhook(wh.id, { is_active: !wh.is_active });
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("asys.hooks.toggleFailed"));
    }
  };

  const secretNote = t("asys.hooks.secretHint");
  return (
    <PageLayout title={t("asys.hooks.title")} subtitle={t("asys.hooks.subtitle")}>
      <Toast {...toast} />
      <div className="stack">
        <section className="panel">
          <div className="panel-head">
            <h2>{editId ? t("asys.hooks.formEdit") : t("asys.hooks.formNew")}</h2>
          </div>
          <form className="panel-body" onSubmit={handleSubmit}>
            {error && (
              <div className="banner banner-danger" role="alert">
                <span className="dot dot-danger" aria-hidden="true" />
                <span className="banner-text">{error}</span>
                <button type="button" className="btn btn-sm" onClick={() => setError(null)}>{t("common.close")}</button>
              </div>
            )}
            <div className="field">
              <label htmlFor="wh-url">{t("asys.hooks.url")} *</label>
              <input id="wh-url" className="inp" type="url" value={endpointUrl}
                onChange={(e) => setEndpointUrl(e.target.value)}
                placeholder={t("asys.hooks.urlPlaceholder")} required />
            </div>

            <div className="field">
              <label htmlFor="wh-desc">{t("asys.hooks.description")}</label>
              <input id="wh-desc" className="inp" type="text" value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("asys.hooks.descriptionPlaceholder")} />
            </div>

            <fieldset className="fieldset">
              <legend style={{ fontSize: "var(--fs-small)", fontWeight: 500, marginBottom: 6 }}>
                {t("asys.hooks.events")} * ({t("asys.hooks.eventsCount", { n: selectedEvents.length })})
              </legend>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {availableEvents.map((ev) => {
                  const on = selectedEvents.includes(ev.event);
                  return (
                    <label key={ev.event} title={ev.description} className="mono"
                      style={{
                        display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer",
                        padding: "3px 8px", borderRadius: "var(--radius-badge)", fontSize: "var(--fs-hint)",
                        background: on ? "var(--accent-soft)" : "var(--surface-2)",
                        border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`,
                        fontWeight: on ? 500 : 400,
                      }}>
                      <input type="checkbox" checked={on} onChange={() => toggleEvent(ev.event)} style={{ accentColor: "var(--accent)" }} />
                      {ev.event}
                    </label>
                  );
                })}
              </div>
            </fieldset>

            <div className="field">
              <label htmlFor="wh-secret">{t("asys.hooks.secret")}</label>
              <input id="wh-secret" className="inp mono" type="text" value={secretToken} autoComplete="off"
                onChange={(e) => setSecretToken(e.target.value)}
                placeholder={t("asys.hooks.secretPlaceholder")} aria-describedby="wh-secret-hint" />
              <p id="wh-secret-hint" className="hint">{secretNote}</p>
            </div>

            <label style={{ display: "inline-flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} style={{ accentColor: "var(--accent)" }} />
              {t("asys.hooks.active")}
            </label>

            <div className="row-actions">
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? "…" : editId ? t("asys.hooks.update") : t("asys.hooks.create")}
              </button>
              {editId && (
                <button type="button" className="btn" onClick={resetForm}>{t("asys.hooks.cancel")}</button>
              )}
            </div>
          </form>
        </section>

        {loading ? (
          <p className="hint" role="status" aria-busy="true">{t("asys.hooks.loading")}</p>
        ) : webhooks.length === 0 ? (
          <div className="card-empty">{t("asys.hooks.empty")}</div>
        ) : (
          <section className="panel">
            <div className="panel-head"><h2>{t("asys.hooks.listTitle")}</h2></div>
            <div role="region" aria-label={t("asys.hooks.tableLabel")} tabIndex={0} style={{ overflowX: "auto" }}>
              <table className="tbl tbl-cards">
                <thead>
                  <tr>
                    <th scope="col">{t("asys.hooks.colUrl")}</th>
                    <th scope="col">{t("asys.hooks.colDescription")}</th>
                    <th scope="col">{t("asys.hooks.colEvents")}</th>
                    <th scope="col">{t("asys.hooks.colStatus")}</th>
                    <th scope="col">{t("asys.hooks.colActions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {webhooks.map((wh) => (
                    <tr key={wh.id}>
                      <td data-label={t("asys.hooks.colUrl")}><span className="mono" style={{ overflowWrap: "anywhere" }}>{wh.endpoint_url}</span></td>
                      <td data-label={t("asys.hooks.colDescription")}>{wh.description || "–"}</td>
                      <td data-label={t("asys.hooks.colEvents")}>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, justifyContent: "inherit" }}>
                          {(wh.events || []).map((ev) => (
                            <span key={ev} className="mono" style={{
                              padding: "1px 6px", borderRadius: "var(--radius-badge)", background: "var(--accent-soft)",
                              fontSize: "var(--fs-hint)",
                            }}>{ev}</span>
                          ))}
                        </div>
                      </td>
                      <td data-label={t("asys.hooks.colStatus")}>
                        <button type="button" className="btn btn-ghost btn-sm" style={{ padding: 0 }}
                          aria-label={t("asys.hooks.toggle", { url: wh.endpoint_url })}
                          title={t("asys.hooks.toggle", { url: wh.endpoint_url })}
                          onClick={() => handleToggleActive(wh)}>
                          <StatusBadge status={wh.is_active ? "active" : "inactive"} size="sm" />
                        </button>
                      </td>
                      <td data-label={t("asys.hooks.colActions")}>
                        <div className="row-actions" style={{ marginTop: 0 }}>
                          <button type="button" className="btn btn-sm btn-icon" onClick={() => startEdit(wh)}
                            aria-label={t("asys.hooks.editAria", { url: wh.endpoint_url })} title={t("asys.hooks.edit")}>
                            <Icon name="pencil" />
                          </button>
                          <button type="button" className="btn btn-sm" onClick={() => handleTest(wh.id)}
                            aria-label={t("asys.hooks.testAria", { url: wh.endpoint_url })}>
                            {t("asys.hooks.test")}
                          </button>
                          <ConfirmButton
                            label={t("asys.hooks.delete")}
                            confirmMessage={t("asys.hooks.deleteConfirm", { url: wh.endpoint_url })}
                            onConfirm={() => handleDelete(wh.id)}
                            danger
                            size="sm"
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </PageLayout>
  );
}
