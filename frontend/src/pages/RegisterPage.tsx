import { useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { t } from "../i18n";
import { api, isAuthenticated, setAccessToken, MIN_PASSWORD_LENGTH } from "../services/api";
import { inputStyle, labelStyle, btnPrimary, linkStyle } from "../components/ui";
import { safeRedirectPath } from "../lib/redirect";
import { AuthCard, AuthMessage } from "../components/AuthCard";

export function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTo = safeRedirectPath(searchParams.get("redirect"));
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);
  const [verifyPending, setVerifyPending] = useState(false);
  const [resent, setResent] = useState(false);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated()) return <Navigate to={redirectTo} replace />;

  const validate = (): string | null => {
    if (!username.trim() || !email.trim() || !password) return t("auth.reg.missing");
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return t("auth.emailInvalid");
    if (password.length < MIN_PASSWORD_LENGTH) return `Das Passwort muss mindestens ${MIN_PASSWORD_LENGTH} Zeichen lang sein`;
    if (password !== confirm) return t("auth.pwMismatch");
    if (!acceptedTerms) return t("auth.reg.terms");
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
        navigate(redirectTo);
      } else {
        // E-Mail-Verifizierung aktiv: erst nach Klick auf den Link in der Mail ist ein Login möglich
        setVerifyPending(true);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t("auth.reg.failed");
      // 403 kommt mit "Registrierung ist deaktiviert"; ein fehlender Endpunkt (404) bedeutet dasselbe
      if (/deaktiviert|403|404/.test(message)) setDisabled(true);
      else setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard title={t("auth.login.register")}>
      {verifyPending ? (
        <>
          <AuthMessage kind="success">
            {t("auth.reg.verifyPending", { email: email.trim() })}
          </AuthMessage>
          {resent && <AuthMessage kind="success">{t("auth.reg.resentOk")}</AuthMessage>}
          <p style={{ textAlign: "center", fontSize: 14 }}>
            {t("auth.reg.nothing")}{" "}
            <button type="button" style={{ ...linkStyle, background: "none", border: "none", padding: 0, cursor: "pointer", font: "inherit" }}
              onClick={async () => {
                try { await api.resendVerification(email.trim()); setResent(true); } catch { /* neutral */ }
              }}>
              {t("auth.reg.resend")}
            </button>
          </p>
          <p style={{ textAlign: "center" }}><Link to="/login" style={linkStyle}>{t("auth.toLogin")}</Link></p>
        </>
      ) : disabled ? (
        <>
          <AuthMessage kind="warning">{t("auth.reg.disabled")}</AuthMessage>
          <p style={{ textAlign: "center" }}><Link to="/login" style={linkStyle}>{t("auth.backToLogin")}</Link></p>
        </>
      ) : (
        <form onSubmit={handleSubmit} noValidate>
          {error && <AuthMessage kind="error">{error}</AuthMessage>}

          <div style={{ marginBottom: 16 }}>
            <label htmlFor="username" style={labelStyle}>{t("auth.username")}</label>
            <input id="username" type="text" autoComplete="username" autoFocus value={username}
              onChange={(e) => setUsername(e.target.value)} style={inputStyle} />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label htmlFor="email" style={labelStyle}>{t("auth.email")}</label>
            <input id="email" type="email" autoComplete="email" value={email}
              onChange={(e) => setEmail(e.target.value)} style={inputStyle} />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label htmlFor="password" style={labelStyle}>{t("auth.password")}</label>
            <input id="password" type="password" autoComplete="new-password" value={password}
              onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
            <small style={{ color: "var(--fg-muted)", fontSize: 12 }}>{t("auth.minLength", { n: MIN_PASSWORD_LENGTH })}</small>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label htmlFor="confirm" style={labelStyle}>{t("auth.pwRepeat")}</label>
            <input id="confirm" type="password" autoComplete="new-password" value={confirm}
              onChange={(e) => setConfirm(e.target.value)} style={inputStyle} />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label htmlFor="terms" style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13, lineHeight: 1.4 }}>
              <input id="terms" type="checkbox" checked={acceptedTerms} required aria-required="true"
                onChange={(e) => setAcceptedTerms(e.target.checked)} style={{ marginTop: 2 }} />
              <span>
                {t("auth.reg.accept")}{" "}
                <Link to="/agb" target="_blank" rel="noopener noreferrer" style={linkStyle}>{t("auth.reg.termsLink")}</Link>
                {" "}{t("auth.reg.and")}{" "}
                <Link to="/datenschutz" target="_blank" rel="noopener noreferrer" style={linkStyle}>{t("auth.reg.privacy")}</Link>.
              </span>
            </label>
          </div>

          <button type="submit" disabled={loading}
            style={{ ...btnPrimary, width: "100%", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1 }}>
            {loading ? t("auth.reg.busy") : t("auth.login.register")}
          </button>
          <p style={{ textAlign: "center", fontSize: 14 }}>
            {t("auth.reg.have")} <Link to={redirectTo === "/" ? "/login" : `/login?redirect=${encodeURIComponent(redirectTo)}`} style={linkStyle}>{t("auth.login.submit")}</Link>
          </p>
        </form>
      )}
    </AuthCard>
  );
}
