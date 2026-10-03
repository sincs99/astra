import { useState } from "react";
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
    if (!current || !next) return setError("Bitte alle Felder ausfüllen");
    if (next.length < MIN_PASSWORD_LENGTH) return setError(`Das neue Passwort muss mindestens ${MIN_PASSWORD_LENGTH} Zeichen lang sein`);
    if (next === current) return setError("Das neue Passwort muss sich vom aktuellen unterscheiden");
    if (next !== confirm) return setError("Die neuen Passwörter stimmen nicht überein");
    try {
      setBusy(true);
      setError(null);
      await api.changePassword(current, next);
      setCurrent(""); setNext(""); setConfirm("");
      onChanged("Passwort geändert.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Passwort konnte nicht geändert werden");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section style={cardStyle} aria-labelledby="pw-title">
      <h2 id="pw-title" style={{ marginTop: 0, fontSize: 18 }}>Passwort ändern</h2>
      {error && <ErrorState message={error} />}
      <form onSubmit={submit} noValidate style={{ maxWidth: 360 }}>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="pw-current" style={labelStyle}>Aktuelles Passwort</label>
          <input id="pw-current" type="password" autoComplete="current-password" value={current}
            onChange={(e) => setCurrent(e.target.value)} style={inputStyle} />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="pw-new" style={labelStyle}>Neues Passwort</label>
          <input id="pw-new" type="password" autoComplete="new-password" value={next}
            onChange={(e) => setNext(e.target.value)} style={inputStyle} />
          <small style={{ color: "#666", fontSize: 12 }}>Mindestens {MIN_PASSWORD_LENGTH} Zeichen</small>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label htmlFor="pw-confirm" style={labelStyle}>Neues Passwort wiederholen</label>
          <input id="pw-confirm" type="password" autoComplete="new-password" value={confirm}
            onChange={(e) => setConfirm(e.target.value)} style={inputStyle} />
        </div>
        <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
          {busy ? "..." : "Passwort ändern"}
        </button>
      </form>
      <p style={{ color: "#666", fontSize: 12, margin: "12px 0 0" }}>
        Hinweis: Bestehende Sitzungen auf anderen Geräten bleiben bis zum Ablauf ihres Tokens gültig.
      </p>
    </section>
  );
}
