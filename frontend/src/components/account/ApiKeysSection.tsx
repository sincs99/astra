import { useEffect, useState } from "react";
import { api, type ApiKeyCreated, type ApiKeyEntry } from "../../services/api";
import {
  cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, thStyle, tdStyle,
  ConfirmButton, ErrorState, LoadingState, EmptyState,
} from "../ui";

/** API-Keys verwalten; der Klartext-Token wird nur direkt nach dem Anlegen angezeigt. */
export function ApiKeysSection({ onMessage }: { onMessage: (message: string) => void }) {
  const [keys, setKeys] = useState<ApiKeyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [memo, setMemo] = useState("");
  const [keyType, setKeyType] = useState<"account" | "application">("account");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const load = async () => {
    try {
      setError(null);
      setKeys(await api.getApiKeys());
    } catch (err) {
      setError(err instanceof Error ? err.message : "API-Keys konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setBusy(true);
      setError(null);
      const result = await api.createApiKey({ key_type: keyType, memo: memo.trim() || undefined });
      setCreated(result);
      setCopied(false);
      setMemo("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "API-Key konnte nicht erstellt werden");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (key: ApiKeyEntry) => {
    try {
      await api.deleteApiKey(key.id);
      if (created?.id === key.id) setCreated(null);
      onMessage("API-Key geloescht.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Loeschen fehlgeschlagen");
    }
  };

  const copyToken = async () => {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.raw_token);
      setCopied(true);
    } catch {
      // Token bleibt markierbar
    }
  };

  return (
    <section style={cardStyle} aria-labelledby="keys-title">
      <h2 id="keys-title" style={{ marginTop: 0, fontSize: 18 }}>API-Keys</h2>
      {error && <ErrorState message={error} onRetry={load} />}

      {created && (
        <div role="alert" style={{ padding: 12, marginBottom: 12, background: "#e8f5e9", border: "1px solid #a5d6a7", borderRadius: 8 }}>
          <strong>Dein neuer API-Key</strong>
          <p style={{ margin: "4px 0 8px", fontSize: 13 }}>
            Kopiere ihn jetzt – er wird <strong>nur einmal</strong> angezeigt und kann danach nicht mehr abgerufen werden.
          </p>
          <code style={{ display: "block", wordBreak: "break-all", userSelect: "all", background: "#fff", padding: 8, borderRadius: 4 }}>
            {created.raw_token}
          </code>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button type="button" onClick={copyToken} style={btnDefault}>{copied ? "✓ Kopiert" : "📋 Kopieren"}</button>
            <button type="button" onClick={() => setCreated(null)} style={btnDefault}>Schliessen</button>
          </div>
        </div>
      )}

      <form onSubmit={create} style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 16 }}>
        <div style={{ flex: 1, minWidth: 180 }}>
          <label htmlFor="key-memo" style={labelStyle}>Beschreibung</label>
          <input id="key-memo" type="text" value={memo} onChange={(e) => setMemo(e.target.value)}
            placeholder="z.B. Backup-Skript" style={inputStyle} />
        </div>
        <div>
          <label htmlFor="key-type" style={labelStyle}>Typ</label>
          <select id="key-type" value={keyType} onChange={(e) => setKeyType(e.target.value as "account" | "application")} style={{ ...inputStyle, width: 150 }}>
            <option value="account">account</option>
            <option value="application">application</option>
          </select>
        </div>
        <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>Key erstellen</button>
      </form>

      {loading ? <LoadingState /> : keys.length === 0 ? (
        <EmptyState icon="🔑" message="Noch keine API-Keys." />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <caption style={{ position: "absolute", left: -9999 }}>Deine API-Keys</caption>
            <thead>
              <tr>
                <th scope="col" style={thStyle}>Kennung</th>
                <th scope="col" style={thStyle}>Beschreibung</th>
                <th scope="col" style={thStyle}>Typ</th>
                <th scope="col" style={thStyle}>Zuletzt genutzt</th>
                <th scope="col" style={thStyle}><span style={{ position: "absolute", left: -9999 }}>Aktionen</span></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td style={tdStyle}><code>{k.identifier}</code></td>
                  <td style={tdStyle}>{k.memo || "–"}</td>
                  <td style={tdStyle}>{k.key_type}</td>
                  <td style={tdStyle}>{k.last_used_at ? new Date(k.last_used_at).toLocaleString("de-CH") : "nie"}</td>
                  <td style={tdStyle}>
                    <ConfirmButton label="Loeschen" danger size="sm"
                      confirmMessage={`API-Key ${k.identifier} wirklich loeschen? Programme, die ihn nutzen, verlieren den Zugriff.`}
                      onConfirm={() => remove(k)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
