import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { t } from "../i18n";
import { api, ApiError } from "../services/api";
import { inputStyle, labelStyle, btnPrimary, linkStyle } from "../components/ui";
import { AuthCard, AuthMessage } from "../components/AuthCard";
import { CaptchaWidget } from "../components/CaptchaWidget";
import { NO_CAPTCHA, type CaptchaConfig } from "../lib/captcha";
import { useRateLimit } from "../hooks/useRateLimit";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [captcha, setCaptcha] = useState<CaptchaConfig>(NO_CAPTCHA);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const rate = useRateLimit();

  useEffect(() => {
    let cancelled = false;
    api.getCaptchaConfig().then((c) => { if (!cancelled) setCaptcha(c); });
    return () => { cancelled = true; };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError(t("auth.emailInvalid"));
      return;
    }
    if (captcha.provider !== "none" && !captchaToken) {
      setError(t("auth.captcha.required"));
      return;
    }
    try {
      setLoading(true);
      setError(null);
      if (captcha.provider !== "none" && captchaToken) await api.requestPasswordReset(email.trim(), captchaToken);
      else await api.requestPasswordReset(email.trim());
      setSent(true);
    } catch (err) {
      if (captcha.provider !== "none") { setCaptchaToken(null); setCaptchaReset((n) => n + 1); }
      if (rate.apply(err)) return;
      if (err instanceof ApiError && err.code === "captcha_failed") { setError(t("auth.captcha.failed")); return; }
      if (err instanceof ApiError && err.code === "captcha_unavailable") { setError(t("auth.captcha.unavailable")); return; }
      setError(err instanceof Error ? err.message : t("auth.forgot.failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard title={t("auth.forgot.title")}>
      {sent ? (
        // Antwort ist bewusst neutral: sie verrät nicht, ob die Adresse existiert
        <AuthMessage kind="success">
          {t("auth.forgot.sent")}
        </AuthMessage>
      ) : (
        <form onSubmit={handleSubmit} noValidate>
          {error && <AuthMessage kind="error">{error}</AuthMessage>}
          {rate.message && <AuthMessage kind="warning">{rate.message}</AuthMessage>}
          <div style={{ marginBottom: 20 }}>
            <label htmlFor="email" style={labelStyle}>{t("auth.email")}</label>
            <input id="email" type="email" autoComplete="email" autoFocus value={email}
              onChange={(e) => setEmail(e.target.value)} style={inputStyle} />
          </div>
          <CaptchaWidget config={captcha} onToken={setCaptchaToken} resetKey={captchaReset} />
          <button type="submit" disabled={loading || rate.blocked}
            style={{ ...btnPrimary, width: "100%", cursor: loading || rate.blocked ? "not-allowed" : "pointer", opacity: loading || rate.blocked ? 0.7 : 1 }}>
            {loading ? t("auth.forgot.busy") : t("auth.forgot.submit")}
          </button>
        </form>
      )}
      <p style={{ textAlign: "center", fontSize: 14 }}>
        <Link to="/login" style={linkStyle}>{t("auth.backToLogin")}</Link>
      </p>
    </AuthCard>
  );
}
