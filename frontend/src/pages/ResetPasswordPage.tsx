import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { t } from "../i18n";
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
      <AuthCard title={t("auth.reset.titleInvalid")}>
        <AuthMessage kind="error">{t("auth.reset.noToken")}</AuthMessage>
        <p style={{ textAlign: "center", fontSize: 14 }}>
          <Link to="/password-reset" style={linkStyle}>{t("auth.reset.newLink")}</Link>
        </p>
      </AuthCard>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(t("auth.reset.tooShort", { n: MIN_PASSWORD_LENGTH }));
      return;
    }
    if (password !== confirm) {
      setError(t("auth.pwMismatch"));
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await api.confirmPasswordReset(token, password);
      navigate("/login?reset=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.reset.failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard title={t("auth.reset.title")}>
      <form onSubmit={handleSubmit} noValidate>
        {error && <AuthMessage kind="error">{error}</AuthMessage>}
        <div style={{ marginBottom: 16 }}>
          <label htmlFor="password" style={labelStyle}>{t("auth.reset.newPw")}</label>
          <input id="password" type="password" autoComplete="new-password" autoFocus value={password}
            onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
          <small style={{ color: "var(--fg-muted)", fontSize: 12 }}>{t("auth.minLength", { n: MIN_PASSWORD_LENGTH })}</small>
        </div>
        <div style={{ marginBottom: 20 }}>
          <label htmlFor="confirm" style={labelStyle}>{t("auth.pwRepeat")}</label>
          <input id="confirm" type="password" autoComplete="new-password" value={confirm}
            onChange={(e) => setConfirm(e.target.value)} style={inputStyle} />
        </div>
        <button type="submit" disabled={loading}
          style={{ ...btnPrimary, width: "100%", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1 }}>
          {loading ? t("auth.reset.busy") : t("auth.reset.submit")}
        </button>
      </form>
    </AuthCard>
  );
}
