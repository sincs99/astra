import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { getLang, t } from "../i18n";
import { api, ApiError, isAuthenticated, setAccessToken, MIN_PASSWORD_LENGTH } from "../services/api";
import { inputStyle, labelStyle, btnPrimary, linkStyle } from "../components/ui";
import { safeRedirectPath } from "../lib/redirect";
import { AuthCard, AuthMessage } from "../components/AuthCard";
import { CaptchaWidget } from "../components/CaptchaWidget";
import { Honeypot } from "../components/Honeypot";
import { NO_CAPTCHA, type CaptchaConfig } from "../lib/captcha";
import { useRateLimit } from "../hooks/useRateLimit";

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
  const [website, setWebsite] = useState("");
  const [captcha, setCaptcha] = useState<CaptchaConfig>(NO_CAPTCHA);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const rate = useRateLimit();

  useEffect(() => {
    let cancelled = false;
    api.getCaptchaConfig().then((c) => { if (!cancelled) setCaptcha(c); });
    return () => { cancelled = true; };
  }, []);

  if (isAuthenticated()) return <Navigate to={redirectTo} replace />;

  const validate = (): string | null => {
    if (!username.trim() || !email.trim() || !password) return t("auth.reg.missing");
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return t("auth.emailInvalid");
    if (password.length < MIN_PASSWORD_LENGTH) return `Das Passwort muss mindestens ${MIN_PASSWORD_LENGTH} Zeichen lang sein`;
    if (password !== confirm) return t("auth.pwMismatch");
    if (!acceptedTerms) return t("auth.reg.terms");
    if (captcha.provider !== "none" && !captchaToken) return t("auth.captcha.required");
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Köder-Feld gefüllt: ein Bot, es wird nichts gesendet
    if (website) return;
    const problem = validate();
    if (problem) { setError(problem); return; }

    try {
      setLoading(true);
      setError(null);
      const result = captcha.provider !== "none" && captchaToken
        ? await api.register(username.trim(), email.trim(), password, getLang(), { captcha_token: captchaToken })
        : await api.register(username.trim(), email.trim(), password, getLang());
      if ("access_token" in result) {
        setAccessToken(result.access_token);
        navigate(redirectTo);
      } else {
        // E-Mail-Verifizierung aktiv: erst nach Klick auf den Link in der Mail ist ein Login möglich
        setVerifyPending(true);
      }
    } catch (err) {
      if (captcha.provider !== "none") { setCaptchaToken(null); setCaptchaReset((n) => n + 1); }
      if (rate.apply(err)) return;
      if (err instanceof ApiError && err.code === "captcha_failed") { setError(t("auth.captcha.failed")); return; }
      if (err instanceof ApiError && err.code === "captcha_unavailable") { setError(t("auth.captcha.unavailable")); return; }
      const message = err instanceof Error ? err.message : t("auth.reg.failed");
      // 403 ("Registrierung ist deaktiviert") und ein fehlender Endpunkt (404) bedeuten dasselbe; erkannt am Status, nicht am Text
      if (err instanceof ApiError && (err.status === 403 || err.status === 404)) setDisabled(true);
      else if (/deaktiviert|403|404/.test(message)) setDisabled(true);
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
          {rate.message && <AuthMessage kind="warning">{rate.message}</AuthMessage>}

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
            <small style={{ color: "var(--text-3)", fontSize: 12 }}>{t("auth.minLength", { n: MIN_PASSWORD_LENGTH })}</small>
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

          <Honeypot value={website} onChange={setWebsite} />
          <CaptchaWidget config={captcha} onToken={setCaptchaToken} resetKey={captchaReset} />

          <button type="submit" disabled={loading || rate.blocked}
            style={{ ...btnPrimary, width: "100%", cursor: loading || rate.blocked ? "not-allowed" : "pointer", opacity: loading || rate.blocked ? 0.7 : 1 }}>
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
