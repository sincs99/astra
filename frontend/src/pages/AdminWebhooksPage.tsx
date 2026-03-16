import { useEffect, useState } from "react";
import {
  api,
  type WebhookEntry,
  type WebhookEventInfo,
} from "../services/api";

export function AdminWebhooksPage() {
  const [webhooks, setWebhooks] = useState<WebhookEntry[]>([]);
  const [availableEvents, setAvailableEvents] = useState<WebhookEventInfo[]>(
    []
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Formular
  const [editId, setEditId] = useState<number | null>(null);
  const [endpointUrl, setEndpointUrl] = useState("");
  const [description, setDescription] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [secretToken, setSecretToken] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // ── Daten laden ──────────────────────────────────────

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

  useEffect(() => {
    loadAll();
  }, []);

  // ── Formular-Logik ───────────────────────────────────

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
    setError(null);
    setSuccess(null);
  };

  const toggleEvent = (event: string) => {
    setSelectedEvents((prev) =>
      prev.includes(event)
        ? prev.filter((e) => e !== event)
        : [...prev, event]
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
      setSuccess(null);

      if (editId) {
        await api.updateWebhook(editId, {
          endpoint_url: endpointUrl.trim(),
          description: description.trim() || undefined,
          events: selectedEvents,
          secret_token: secretToken || undefined,
          is_active: isActive,
        });
        setSuccess("Webhook aktualisiert");
      } else {
        await api.createWebhook({
          endpoint_url: endpointUrl.trim(),
          description: description.trim() || undefined,
          events: selectedEvents,
          secret_token: secretToken.trim() || undefined,
          is_active: isActive,
        });
        setSuccess("Webhook erstellt");
      }

      resetForm();
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Speichern");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Webhook wirklich löschen?")) return;
    try {
      setError(null);
      setSuccess(null);
      await api.deleteWebhook(id);
      setSuccess("Webhook gelöscht");
      if (editId === id) resetForm();
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Löschen");
    }
  };

  const handleTest = async (id: number) => {
    try {
      setError(null);
      setSuccess(null);
      const result = await api.testWebhook(id);
      if (result.success) {
        setSuccess(`Test erfolgreich: ${result.message}`);
      } else {
        setError(`Test fehlgeschlagen: ${result.message}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Testen");
    }
  };

  const handleToggleActive = async (wh: WebhookEntry) => {
    try {
      setError(null);
      await api.updateWebhook(wh.id, { is_active: !wh.is_active });
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Umschalten");
    }
  };

  // ── Render ───────────────────────────────────────────

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>Webhooks</h1>

      {/* Formular */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0 }}>
          {editId ? "Webhook bearbeiten" : "Neuer Webhook"}
        </h2>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Endpoint-URL *</label>
            <input
              type="url"
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
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
              onChange={(e) => setDescription(e.target.value)}
              placeholder="z.B. Slack-Benachrichtigung"
              style={{ ...inputStyle, width: "100%" }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={labelStyle}>Events *</label>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                padding: 8,
                border: "1px solid #444",
                borderRadius: 6,
                backgroundColor: "#1e1e1e",
              }}
            >
              {availableEvents.map((ev) => (
                <label
                  key={ev.event}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    cursor: "pointer",
                    padding: "4px 8px",
                    borderRadius: 4,
                    backgroundColor: selectedEvents.includes(ev.event)
                      ? "#2a6496"
                      : "#333",
                    color: "#eee",
                    fontSize: 13,
                  }}
                  title={ev.description}
                >
                  <input
                    type="checkbox"
                    checked={selectedEvents.includes(ev.event)}
                    onChange={() => toggleEvent(ev.event)}
                    style={{ accentColor: "#5cb85c" }}
                  />
                  {ev.event}
                </label>
              ))}
            </div>
            <small style={{ color: "#888" }}>
              {selectedEvents.length} Event(s) ausgewählt
            </small>
          </div>

          <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Secret Token</label>
              <input
                type="text"
                value={secretToken}
                onChange={(e) => setSecretToken(e.target.value)}
                placeholder="Wird automatisch generiert"
                style={{ ...inputStyle, width: "100%" }}
              />
              <small style={{ color: "#888" }}>
                Leer lassen für automatische Generierung
              </small>
            </div>
            <div>
              <label style={labelStyle}>Status</label>
              <div style={{ paddingTop: 6 }}>
                <label style={{ cursor: "pointer", color: "#eee" }}>
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                    style={{ accentColor: "#5cb85c", marginRight: 6 }}
                  />
                  Aktiv
                </label>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={submitting} style={btnStyle}>
              {submitting
                ? "…"
                : editId
                ? "Webhook aktualisieren"
                : "Webhook erstellen"}
            </button>
            {editId && (
              <button
                type="button"
                onClick={resetForm}
                style={{ ...btnStyle, backgroundColor: "#666" }}
              >
                Abbrechen
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Meldungen */}
      {error && <div style={errorStyle}>{error}</div>}
      {success && <div style={successStyle}>{success}</div>}

      {/* Webhook-Liste */}
      {loading ? (
        <p>Wird geladen...</p>
      ) : webhooks.length === 0 ? (
        <p style={{ color: "#888" }}>Noch keine Webhooks vorhanden.</p>
      ) : (
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>URL</th>
              <th style={thStyle}>Beschreibung</th>
              <th style={thStyle}>Events</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {webhooks.map((wh) => (
              <tr key={wh.id}>
                <td style={tdStyle}>
                  <span
                    style={{
                      fontFamily: "monospace",
                      fontSize: 13,
                      wordBreak: "break-all",
                    }}
                  >
                    {wh.endpoint_url}
                  </span>
                </td>
                <td style={tdStyle}>{wh.description || "–"}</td>
                <td style={tdStyle}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                    {(wh.events || []).map((ev) => (
                      <span key={ev} style={eventBadge}>
                        {ev}
                      </span>
                    ))}
                  </div>
                </td>
                <td style={tdStyle}>
                  <span
                    style={{
                      ...badge,
                      backgroundColor: wh.is_active ? "#5cb85c" : "#999",
                      cursor: "pointer",
                    }}
                    onClick={() => handleToggleActive(wh)}
                    title="Klicken zum Umschalten"
                  >
                    {wh.is_active ? "aktiv" : "inaktiv"}
                  </span>
                </td>
                <td style={tdStyle}>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button
                      onClick={() => startEdit(wh)}
                      style={smallBtnStyle}
                      title="Bearbeiten"
                    >
                      ✏️
                    </button>
                    <button
                      onClick={() => handleTest(wh.id)}
                      style={smallBtnStyle}
                      title="Test senden"
                    >
                      🧪
                    </button>
                    <button
                      onClick={() => handleDelete(wh.id)}
                      style={{ ...smallBtnStyle, backgroundColor: "#d9534f" }}
                      title="Löschen"
                    >
                      🗑️
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────

const cardStyle: React.CSSProperties = {
  backgroundColor: "#1a1a2e",
  border: "1px solid #333",
  borderRadius: 8,
  padding: 20,
  marginBottom: 16,
};

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: 4,
  fontSize: 13,
  color: "#aaa",
};

const inputStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: 6,
  border: "1px solid #444",
  backgroundColor: "#1e1e1e",
  color: "#eee",
  fontSize: 14,
  boxSizing: "border-box",
};

const btnStyle: React.CSSProperties = {
  padding: "8px 20px",
  borderRadius: 6,
  border: "none",
  backgroundColor: "#5cb85c",
  color: "#fff",
  fontWeight: 600,
  cursor: "pointer",
  fontSize: 14,
};

const smallBtnStyle: React.CSSProperties = {
  padding: "4px 8px",
  borderRadius: 4,
  border: "none",
  backgroundColor: "#444",
  color: "#fff",
  cursor: "pointer",
  fontSize: 13,
};

const errorStyle: React.CSSProperties = {
  backgroundColor: "#5a1a1a",
  border: "1px solid #d9534f",
  color: "#f99",
  padding: 12,
  borderRadius: 6,
  marginBottom: 12,
};

const successStyle: React.CSSProperties = {
  backgroundColor: "#1a3a1a",
  border: "1px solid #5cb85c",
  color: "#9f9",
  padding: 12,
  borderRadius: 6,
  marginBottom: 12,
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  backgroundColor: "#1a1a2e",
  borderRadius: 8,
  overflow: "hidden",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  borderBottom: "2px solid #333",
  color: "#aaa",
  fontSize: 13,
  fontWeight: 600,
};

const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
  borderBottom: "1px solid #333",
  color: "#eee",
  fontSize: 14,
  verticalAlign: "top",
};

const badge: React.CSSProperties = {
  display: "inline-block",
  padding: "2px 8px",
  borderRadius: 4,
  color: "#fff",
  fontSize: 12,
  fontWeight: 600,
};

const eventBadge: React.CSSProperties = {
  display: "inline-block",
  padding: "2px 6px",
  borderRadius: 4,
  backgroundColor: "#2a4a6a",
  color: "#aad",
  fontSize: 11,
  fontFamily: "monospace",
};
