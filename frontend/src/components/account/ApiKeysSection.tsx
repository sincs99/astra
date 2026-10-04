import { useEffect, useState } from "react";
import { t } from "../../i18n";
import { api, type ApiKeyCreated, type ApiKeyEntry } from "../../services/api";
import {
  cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, thStyle, tdStyle,
  ConfirmButton, ErrorState, LoadingState, EmptyState,
} from "../ui";
import { formatDateTime } from "../../lib/dates";

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
      setError(err instanceof Error ? err.message : t("account.keys.loadFailed"));
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
      setError(err instanceof Error ? err.message : t("account.keys.createFailed"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (key: ApiKeyEntry) => {
    try {
      await api.deleteApiKey(key.id);
      if (created?.id === key.id) setCreated(null);
      onMessage(t("account.keys.deleted"));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("account.keys.deleteFailed"));
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
      <h2 id="keys-title" style={{ marginTop: 0, fontSize: 18 }}>{t("account.keys.title")}</h2>
      {error && <ErrorState message={error} onRetry={load} />}

      {created && (
        <div role="alert" style={{ padding: 12, marginBottom: 12, background: "color-mix(in srgb, var(--ok) 12%, transparent)", border: "1px solid color-mix(in srgb, var(--ok) 35%, transparent)", borderRadius: 8 }}>
          <strong>{t("account.keys.newTitle")}</strong>
          <p style={{ margin: "4px 0 8px", fontSize: 13 }}>
            {t("account.keys.newText1")}<strong>{t("account.keys.once")}</strong>{t("account.keys.newText2")}
          </p>
          <code style={{ display: "block", wordBreak: "break-all", userSelect: "all", background: "var(--surface)", padding: 8, borderRadius: 4 }}>
            {created.raw_token}
          </code>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button type="button" onClick={copyToken} style={btnDefault}>{copied ? "✓ " + t("account.copied") : "📋 " + t("account.copy")}</button>
            <button type="button" onClick={() => setCreated(null)} style={btnDefault}>{t("account.close")}</button>
          </div>
        </div>
      )}

      <form onSubmit={create} style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 16 }}>
        <div style={{ flex: 1, minWidth: 180 }}>
          <label htmlFor="key-memo" style={labelStyle}>{t("account.keys.memo")}</label>
          <input id="key-memo" type="text" value={memo} onChange={(e) => setMemo(e.target.value)}
            placeholder={t("account.keys.memoPh")} style={inputStyle} />
        </div>
        <div>
          <label htmlFor="key-type" style={labelStyle}>{t("account.keys.type")}</label>
          <select id="key-type" value={keyType} onChange={(e) => setKeyType(e.target.value as "account" | "application")} style={{ ...inputStyle, width: 150 }}>
            <option value="account">account</option>
            <option value="application">application</option>
          </select>
        </div>
        <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>{t("account.keys.create")}</button>
      </form>

      {loading ? <LoadingState /> : keys.length === 0 ? (
        <EmptyState icon="🔑" message={t("account.keys.none")} />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <caption style={{ position: "absolute", left: -9999 }}>{t("account.keys.caption")}</caption>
            <thead>
              <tr>
                <th scope="col" style={thStyle}>{t("account.keys.colId")}</th>
                <th scope="col" style={thStyle}>{t("account.keys.memo")}</th>
                <th scope="col" style={thStyle}>{t("account.keys.type")}</th>
                <th scope="col" style={thStyle}>{t("account.keys.colLastUsed")}</th>
                <th scope="col" style={thStyle}><span style={{ position: "absolute", left: -9999 }}>{t("account.keys.colActions")}</span></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td style={tdStyle}><code>{k.identifier}</code></td>
                  <td style={tdStyle}>{k.memo || "–"}</td>
                  <td style={tdStyle}>{k.key_type}</td>
                  <td style={tdStyle}>{k.last_used_at ? formatDateTime(k.last_used_at) : t("account.keys.never")}</td>
                  <td style={tdStyle}>
                    <ConfirmButton label={t("account.delete")} danger size="sm"
                      confirmMessage={t("account.keys.deleteConfirm", { id: k.identifier })}
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
