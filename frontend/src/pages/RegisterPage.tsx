import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api, isAuthenticated, setAccessToken, MIN_PASSWORD_LENGTH } from "../services/api";
import { inputStyle, labelStyle, btnPrimary, linkStyle } from "../components/ui";
import { AuthCard, AuthMessage } from "../components/AuthCard";

export function RegisterPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);
  const [verifyPending, setVerifyPending] = useState(false);
  const [resent, setResent] = useState(false);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated()) return <Navigate to="/" replace />;

  const validate = (): string | null => {
    if (!username.trim() || !email.trim() || !password) return "Bitte alle Felder ausfuellen";
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return "Bitte eine gueltige E-Mail-Adresse eingeben";
    if (password.length < MIN_PASSWORD_LENGTH) return `Das Passwort muss mindestens ${MIN_PASSWORD_LENGTH} Zeichen lang sein`;
    if (password !== confirm) return "Die Passwoerter stimmen nicht ueberein";
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const problem = validate();
    if (problem) { setError(problem); return; }

    try {
      setLoading(true);
      setError(null);
      const result = await api.register(username.trim(), email.trim(), password);
      if ("access_token" in result) {
        setAccessToken(result.access_token);
        navigate("/");
      } else {
        // E-Mail-Verifizierung aktiv: erst nach Klick auf den Link in der Mail ist ein Login moeglich
        setVerifyPending(true);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Registrierung fehlgeschlagen";
      // 403 kommt mit "Registrierung ist deaktiviert"; ein fehlender Endpunkt (404) bedeutet dasselbe
      if (/deaktiviert|403|404/.test(message)) setDisabled(true);
      else setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard title="Konto erstellen">
      {verifyPending ? (
        <>
          <AuthMessage kind="success">
            Fast geschafft: Wir haben eine E-Mail an {email.trim()} geschickt. Bitte klicke auf den Link darin, um deine Adresse zu bestaetigen.
          </AuthMessage>
          {resent && <AuthMessage kind="success">Die E-Mail wurde erneut gesendet.</AuthMessage>}
          <p style={{ textAlign: "center", fontSize: 14 }}>
            Nichts erhalten?{" "}
            <button type="button" style={{ ...linkStyle, background: "none", border: "none", padding: 0, cursor: "pointer", font: "inherit" }}
              onClick={async () => {
                try { await api.resendVerification(email.trim()); setResent(true); } catch { /* neutral */ }
              }}>
              Erneut senden
            </button>
          </p>
          <p style={{ textAlign: "center" }}><Link to="/login" style={linkStyle}>Zum Login</Link></p>
        </>
      ) : disabled ? (
        <>
          <AuthMessage kind="warning">Registrierung ist deaktiviert. Bitte wende dich an einen Administrator.</AuthMessage>
          <p style={{ textAlign: "center" }}><Link to="/login" style={linkStyle}>Zurueck zum Login</Link></p>
        </>
      ) : (
        <form onSubmit={handleSubmit} noValidate>
          {error && <AuthMessage kind="error">{error}</AuthMessage>}

          <div style={{ marginBottom: 16 }}>
            <label htmlFor="username" style={labelStyle}>Benutzername</label>
            <input id="username" type="text" autoComplete="username" autoFocus value={username}
              onChange={(e) => setUsername(e.target.value)} style={inputStyle} />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label htmlFor="email" style={labelStyle}>E-Mail</label>
            <input id="email" type="email" autoComplete="email" value={email}
              onChange={(e) => setEmail(e.target.value)} style={inputStyle} />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label htmlFor="password" style={labelStyle}>Passwort</label>
            <input id="password" type="password" autoComplete="new-password" value={password}
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
            {loading ? "Wird erstellt..." : "Konto erstellen"}
          </button>
          <p style={{ textAlign: "center", fontSize: 14 }}>
            Schon ein Konto? <Link to="/login" style={linkStyle}>Anmelden</Link>
          </p>
        </form>
      )}
    </AuthCard>
  );
}
