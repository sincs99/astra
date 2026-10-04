import { useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { t } from "../i18n";
import { api, ApiError, isAuthenticated, setAccessToken } from "../services/api";
import { SiteFooter } from "../components/SiteFooter";
import { safeRedirectPath } from "../lib/redirect";
import { inputStyle, labelStyle, btnPrimary, linkStyle } from "../components/ui";

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const expired = searchParams.get("expired") === "1";
  const redirectTo = safeRedirectPath(searchParams.get("redirect"));
  const resetDone = searchParams.get("reset") === "1";
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [unverified, setUnverified] = useState(false);
  const [resent, setResent] = useState(false);

  // Bereits eingeloggt -> direkt zum Dashboard (nicht bei abgelaufener Sitzung)
  if (isAuthenticated() && !expired) return <Navigate to={redirectTo} replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!login.trim() || !password.trim()) {
      setError(t("auth.login.missing"));
      return;
    }
    if (mfaRequired && !mfaCode.trim()) {
      setError(t("auth.login.missingCode"));
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setUnverified(false);
      setResent(false);
      const result = await api.login(login.trim(), password, mfaRequired ? mfaCode.trim() : undefined);
      if ("requires_mfa" in result) {
        // Zweiter Schritt: Code aus der Authenticator-App (oder Recovery-Code) abfragen
        setMfaRequired(true);
        return;
      }
      setAccessToken(result.access_token);
      navigate(redirectTo);
    } catch (err) {
      if (err instanceof ApiError && err.code === "email_not_verified") setUnverified(true);
      setError(err instanceof Error ? err.message : t("auth.login.failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "clamp(24px, 10vh, 80px) auto", padding: 24 }}>
      <h1 style={{ textAlign: "center", marginBottom: 24 }}>{t("auth.login.title")}</h1>

      {resetDone && !error && (
        <div role="status" style={{
          padding: "10px 14px", backgroundColor: "var(--tint-green)", color: "var(--c-green)",
          borderRadius: 6, marginBottom: 16, fontSize: 14,
        }}>
          {t("auth.login.resetDone")}
        </div>
      )}

      {expired && !error && (
        <div role="status" style={{
          padding: "10px 14px", backgroundColor: "var(--tint-orange)", color: "var(--c-orange)",
          borderRadius: 6, marginBottom: 16, fontSize: 14,
        }}>
          {t("auth.login.expired")}
        </div>
      )}

      {error && (
        <div role="alert" style={{
          padding: "10px 14px",
          backgroundColor: "var(--tint-red)",
          color: "var(--c-red)",
          borderRadius: 6,
          marginBottom: 16,
          fontSize: 14,
        }}>
          {error}
          {unverified && (
            <div style={{ marginTop: 8 }}>
              {resent ? t("auth.login.resentOk") : (
                <button type="button" style={{ ...linkStyle, background: "none", border: "none", padding: 0, cursor: "pointer", font: "inherit" }}
                  onClick={async () => {
                    try { await api.resendVerification(login.trim()); setResent(true); } catch { /* neutral */ }
                  }}>
                  {t("auth.login.resend")}
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 16 }}>
          <label htmlFor="login" style={labelStyle}>
            {t("auth.login.user")}
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
            {t("auth.password")}
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

        {mfaRequired && (
          <div style={{ marginBottom: 20 }}>
            <label htmlFor="mfa" style={labelStyle}>{t("auth.login.mfaLabel")}</label>
            <input
              id="mfa"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value)}
              placeholder="123456"
              style={inputStyle}
            />
            <small style={{ color: "var(--fg-muted)", fontSize: 12 }}>
              {t("auth.login.mfaHint")}
            </small>
          </div>
        )}

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
          {loading ? t("auth.login.busy") : mfaRequired ? t("auth.login.confirm") : t("auth.login.submit")}
        </button>

        <p style={{ display: "flex", justifyContent: "space-between", fontSize: 14, marginTop: 16 }}>
          <Link to="/password-reset" style={linkStyle}>{t("auth.login.forgot")}</Link>
          <Link to={redirectTo === "/" ? "/register" : `/register?redirect=${encodeURIComponent(redirectTo)}`} style={linkStyle}>{t("auth.login.register")}</Link>
        </p>
      </form>
      <SiteFooter />
    </div>
  );
}
