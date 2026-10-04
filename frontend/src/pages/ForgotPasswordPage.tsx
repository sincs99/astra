import { useState } from "react";
import { Link } from "react-router-dom";
import { t } from "../i18n";
import { api } from "../services/api";
import { inputStyle, labelStyle, btnPrimary, linkStyle } from "../components/ui";
import { AuthCard, AuthMessage } from "../components/AuthCard";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError(t("auth.emailInvalid"));
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await api.requestPasswordReset(email.trim());
      setSent(true);
    } catch (err) {
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
          <div style={{ marginBottom: 20 }}>
            <label htmlFor="email" style={labelStyle}>{t("auth.email")}</label>
            <input id="email" type="email" autoComplete="email" autoFocus value={email}
              onChange={(e) => setEmail(e.target.value)} style={inputStyle} />
          </div>
          <button type="submit" disabled={loading}
            style={{ ...btnPrimary, width: "100%", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1 }}>
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
