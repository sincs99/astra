import { useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { t } from "../i18n";
import { api, ApiError, isAuthenticated, setAccessToken } from "../services/api";
import { SiteFooter } from "../components/SiteFooter";
import { setFlash } from "../lib/flash";
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
  const [useRecovery, setUseRecovery] = useState(false);
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
      setError(t(useRecovery ? "auth.login.missingRecovery" : "auth.login.missingCode"));
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
      if (result.recovery_code_used) {
        // Einmaliger Hinweis nach dem Login: wie viele Codes noch übrig sind (bei wenigen mit Link ins Konto)
        const left = result.recovery_codes_remaining ?? 0;
        setFlash(left <= 2
          ? { kind: "warning", text: t("auth.login.recoveryLow", { n: left }), link: { to: "/account", label: t("auth.login.recoveryLink") } }
          : { kind: "info", text: t("auth.login.recoveryUsed", { n: left }) });
      }
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
            <label htmlFor="mfa" style={labelStyle}>{useRecovery ? t("auth.login.recoveryLabel") : t("auth.login.mfaLabel")}</label>
            <input
              id="mfa"
              type="text"
              inputMode={useRecovery ? "text" : "numeric"}
              autoComplete={useRecovery ? "off" : "one-time-code"}
              autoCapitalize="none"
              spellCheck={false}
              autoFocus
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value)}
              placeholder={useRecovery ? "xxxxx-xxxxx" : "123456"}
              style={inputStyle}
            />
            <small style={{ color: "var(--fg-muted)", fontSize: 12 }}>
              {useRecovery ? t("auth.login.recoveryHint") : t("auth.login.mfaHint")}
            </small>
            <div style={{ marginTop: 6 }}>
              <button type="button" onClick={() => { setUseRecovery(!useRecovery); setMfaCode(""); setError(null); }}
                style={{ ...linkStyle, background: "none", border: "none", padding: 0, cursor: "pointer", font: "inherit", fontSize: 13 }}>
                {useRecovery ? t("auth.login.useApp") : t("auth.login.useRecovery")}
              </button>
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            ...btnPrimary,
            width: "100%",
            backgroundColor: loading ? "var(--neutral)" : btnPrimary.backgroundColor,
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
