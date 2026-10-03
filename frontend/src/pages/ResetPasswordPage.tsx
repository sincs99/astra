import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, MIN_PASSWORD_LENGTH } from "../services/api";
import { inputStyle, labelStyle, btnPrimary, linkStyle } from "../components/ui";
import { AuthCard, AuthMessage } from "../components/AuthCard";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!token) {
    return (
      <AuthCard title="Passwort zuruecksetzen">
        <AuthMessage kind="error">Der Link ist ungueltig, es fehlt der Token.</AuthMessage>
        <p style={{ textAlign: "center", fontSize: 14 }}>
          <Link to="/password-reset" style={linkStyle}>Neuen Link anfordern</Link>
        </p>
      </AuthCard>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Das Passwort muss mindestens ${MIN_PASSWORD_LENGTH} Zeichen lang sein`);
      return;
    }
    if (password !== confirm) {
      setError("Die Passwoerter stimmen nicht ueberein");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await api.confirmPasswordReset(token, password);
      navigate("/login?reset=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Zuruecksetzen fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard title="Neues Passwort setzen">
      <form onSubmit={handleSubmit} noValidate>
        {error && <AuthMessage kind="error">{error}</AuthMessage>}
        <div style={{ marginBottom: 16 }}>
          <label htmlFor="password" style={labelStyle}>Neues Passwort</label>
          <input id="password" type="password" autoComplete="new-password" autoFocus value={password}
            onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
          <small style={{ color: "#666", fontSize: 12 }}>Mindestens {MIN_PASSWORD_LENGTH} Zeichen</small>
        </div>
        <div style={{ marginBottom: 20 }}>
          <label htmlFor="confirm" style={labelStyle}>Passwort wiederholen</label>
          <input id="confirm" type="password" autoComplete="new-password" value={confirm}
            onChange={(e) => setConfirm(e.target.value)} style={inputStyle} />
        </div>
        <button type="submit" disabled={loading}
          style={{ ...btnPrimary, width: "100%", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1 }}>
          {loading ? "Wird gespeichert..." : "Passwort speichern"}
        </button>
      </form>
    </AuthCard>
  );
}
