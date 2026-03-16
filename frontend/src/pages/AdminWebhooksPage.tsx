import { useEffect, useState } from "react";
import { api, type WebhookEntry, type WebhookEventInfo } from "../services/api";
import {
  PageLayout, StatusBadge, LoadingState, EmptyState, ErrorState, ConfirmButton,
  Toast, useToast,
  cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, thStyle, tdStyle,
} from "../components/ui";

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
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
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
      setError("URL und mindestens ein Event sind erforderlich");
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
        toast.success("Webhook aktualisiert.");
      } else {
        await api.createWebhook({
          endpoint_url: endpointUrl.trim(),
          description: description.trim() || undefined,
          events: selectedEvents,
          secret_token: secretToken.trim() || undefined,
          is_active: isActive,
        });
        toast.success("Webhook erstellt.");
      }
      resetForm();
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Speichern");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      setError(null);
      await api.deleteWebhook(id);
      toast.success("Webhook gelöscht.");
      if (editId === id) resetForm();
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Löschen");
    }
  };

  const handleTest = async (id: number) => {
    try {
      const result = await api.testWebhook(id);
      if (result.success) {
        toast.success(`Test erfolgreich: ${result.message}`);
      } else {
        toast.error(`Test fehlgeschlagen: ${result.message}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Testen");
    }
  };

  const handleToggleActive = async (wh: WebhookEntry) => {
    try {
      await api.updateWebhook(wh.id, { is_active: !wh.is_active });
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Umschalten");
    }
  };

  return (
    <PageLayout title="Webhooks">
      <Toast {...toast} />

      {/* Formular */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>
          {editId ? "Webhook bearbeiten" : "Neuer Webhook"}
        </h2>
        {error && <ErrorState message={error} onRetry={() => setError(null)} />}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Endpoint-URL *</label>
            <input
              type="url"
              value={endpointUrl}
              onChange={e => setEndpointUrl(e.target.value)}
              placeholder="https://example.com/webhook"
              required
              style={{ ...inputStyle, width: "100%" }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Beschreibung</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="z.B. Slack-Benachrichtigung"
              style={{ ...inputStyle, width: "100%" }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Events * ({selectedEvents.length} ausgewählt)</label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, padding: 10, border: "1px solid #e0e0e0", borderRadius: 6, backgroundColor: "#fafafa" }}>
              {availableEvents.map(ev => (
                <label
                  key={ev.event}
                  title={ev.description}
                  style={{
                    display: "flex", alignItems: "center", gap: 4, cursor: "pointer",
                    padding: "3px 8px", borderRadius: 4, fontSize: 12,
                    backgroundColor: selectedEvents.includes(ev.event) ? "#e3f2fd" : "#f0f0f0",
                    color: selectedEvents.includes(ev.event) ? "#1976d2" : "#555",
                    fontWeight: selectedEvents.includes(ev.event) ? 600 : 400,
                    border: `1px solid ${selectedEvents.includes(ev.event) ? "#90caf9" : "#ddd"}`,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedEvents.includes(ev.event)}
                    onChange={() => toggleEvent(ev.event)}
                    style={{ accentColor: "#1976d2" }}
                  />
                  {ev.event}
                </label>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 160 }}>
              <label style={labelStyle}>Secret Token</label>
              <input
                type="text"
                value={secretToken}
                onChange={e => setSecretToken(e.target.value)}
                placeholder="Wird automatisch generiert"
                style={{ ...inputStyle, width: "100%" }}
              />
              <small style={{ color: "#888", fontSize: 11 }}>Leer lassen für automatische Generierung</small>
            </div>
            <div>
              <label style={labelStyle}>Status</label>
              <div style={{ paddingTop: 10 }}>
                <label style={{ cursor: "pointer", fontSize: 13 }}>
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={e => setIsActive(e.target.checked)}
                    style={{ marginRight: 6 }}
                  />
                  Aktiv
                </label>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={submitting} style={{ ...btnPrimary, opacity: submitting ? 0.6 : 1 }}>
              {submitting ? "…" : editId ? "Webhook aktualisieren" : "Webhook erstellen"}
            </button>
            {editId && (
              <button type="button" onClick={resetForm} style={btnDefault}>Abbrechen</button>
            )}
          </div>
        </form>
      </div>

      {/* Webhook-Liste */}
      {loading ? (
        <LoadingState message="Webhooks werden geladen..." />
      ) : webhooks.length === 0 ? (
        <EmptyState icon="🔗" message="Noch keine Webhooks vorhanden." />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid #e0e0e0" }}>
            <thead>
              <tr style={{ backgroundColor: "#f5f5f5" }}>
                <th style={thStyle}>URL</th>
                <th style={thStyle}>Beschreibung</th>
                <th style={thStyle}>Events</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {webhooks.map(wh => (
                <tr key={wh.id}>
                  <td style={tdStyle}>
                    <span style={{ fontFamily: "monospace", fontSize: 12, wordBreak: "break-all" }}>
                      {wh.endpoint_url}
                    </span>
                  </td>
                  <td style={tdStyle}>{wh.description || "–"}</td>
                  <td style={tdStyle}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {(wh.events || []).map(ev => (
                        <span key={ev} style={{ display: "inline-block", padding: "2px 6px", borderRadius: 4, backgroundColor: "#e3f2fd", color: "#1976d2", fontSize: 11, fontFamily: "monospace" }}>
                          {ev}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td style={tdStyle}>
                    <span
                      style={{ cursor: "pointer" }}
                      onClick={() => handleToggleActive(wh)}
                      title="Klicken zum Umschalten"
                    >
                      <StatusBadge status={wh.is_active ? "active" : "inactive"} size="sm" />
                    </span>
                  </td>
                  <td style={tdStyle}>
                    <div style={{ display: "flex", gap: 4 }}>
                      <button onClick={() => startEdit(wh)} style={actionBtn} title="Bearbeiten">✏️</button>
                      <button onClick={() => handleTest(wh.id)} style={actionBtn} title="Test senden">🧪</button>
                      <ConfirmButton
                        label="🗑️"
                        confirmMessage={`Webhook "${wh.endpoint_url}" löschen?`}
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
      )}
    </PageLayout>
  );
}

const actionBtn: React.CSSProperties = {
  padding: "4px 8px", borderRadius: 4, border: "1px solid #ddd",
  backgroundColor: "#fff", cursor: "pointer", fontSize: 13,
};
