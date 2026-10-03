import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api, isAuthenticated, setAccessToken } from "../services/api";
import { inputStyle, labelStyle, btnPrimary } from "../components/ui";

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const expired = searchParams.get("expired") === "1";
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Bereits eingeloggt -> direkt zum Dashboard (nicht bei abgelaufener Sitzung)
  if (isAuthenticated() && !expired) return <Navigate to="/" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!login.trim() || !password.trim()) {
      setError("Bitte Username/Email und Passwort eingeben");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const result = await api.login(login.trim(), password);
      setAccessToken(result.access_token);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anmeldung fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "clamp(24px, 10vh, 80px) auto", padding: 24 }}>
      <h1 style={{ textAlign: "center", marginBottom: 24 }}>Astra Login</h1>

      {expired && !error && (
        <div role="status" style={{
          padding: "10px 14px", backgroundColor: "#fff3e0", color: "#e65100",
          borderRadius: 6, marginBottom: 16, fontSize: 14,
        }}>
          Deine Sitzung ist abgelaufen. Bitte melde dich erneut an.
        </div>
      )}

      {error && (
        <div role="alert" style={{
          padding: "10px 14px",
          backgroundColor: "#fce4e4",
          color: "#c0392b",
          borderRadius: 6,
          marginBottom: 16,
          fontSize: 14,
        }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label htmlFor="login" style={labelStyle}>
            Username oder Email
          </label>
          <input
            id="login"
            type="text"
            autoComplete="username"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            placeholder="admin"
            autoFocus
            style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: 20 }}>
          <label htmlFor="password" style={labelStyle}>
            Passwort
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••"
            style={inputStyle}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            ...btnPrimary,
            width: "100%",
            backgroundColor: loading ? "#95a5a6" : btnPrimary.backgroundColor,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Wird angemeldet..." : "Anmelden"}
        </button>
      </form>
    </div>
  );
}
