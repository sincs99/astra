import { useState } from "react";
import { t } from "../../i18n";
import { api, MIN_PASSWORD_LENGTH } from "../../services/api";
import { cardStyle, inputStyle, labelStyle, btnPrimary, ErrorState } from "../ui";

export function PasswordSection({ onChanged }: { onChanged: (message: string) => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!current || !next) return setError(t("account.pw.missing"));
    if (next.length < MIN_PASSWORD_LENGTH) return setError(t("account.pw.tooShort", { n: MIN_PASSWORD_LENGTH }));
    if (next === current) return setError(t("account.pw.same"));
    if (next !== confirm) return setError(t("account.pw.mismatch"));
    try {
      setBusy(true);
      setError(null);
      await api.changePassword(current, next);
      setCurrent(""); setNext(""); setConfirm("");
      onChanged(t("account.pw.changed"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("account.pw.failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section style={cardStyle} aria-labelledby="pw-title">
      <h2 id="pw-title" style={{ marginTop: 0, fontSize: 18 }}>{t("account.pw.title")}</h2>
      {error && <ErrorState message={error} />}
      <form onSubmit={submit} noValidate style={{ maxWidth: 360 }}>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="pw-current" style={labelStyle}>{t("account.pw.current")}</label>
          <input id="pw-current" type="password" autoComplete="current-password" value={current}
            onChange={(e) => setCurrent(e.target.value)} style={inputStyle} />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="pw-new" style={labelStyle}>{t("account.pw.new")}</label>
          <input id="pw-new" type="password" autoComplete="new-password" value={next}
            onChange={(e) => setNext(e.target.value)} style={inputStyle} />
          <small style={{ color: "var(--fg-muted)", fontSize: 12 }}>{t("account.pw.minLength", { n: MIN_PASSWORD_LENGTH })}</small>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label htmlFor="pw-confirm" style={labelStyle}>{t("account.pw.repeat")}</label>
          <input id="pw-confirm" type="password" autoComplete="new-password" value={confirm}
            onChange={(e) => setConfirm(e.target.value)} style={inputStyle} />
        </div>
        <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
          {busy ? "..." : t("account.pw.title")}
        </button>
      </form>
      <p style={{ color: "var(--fg-muted)", fontSize: 12, margin: "12px 0 0" }}>
        {t("account.pw.hint")}
      </p>
    </section>
  );
}
