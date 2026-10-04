import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { t } from "../i18n";
import { api } from "../services/api";
import { linkStyle } from "../components/ui";
import { AuthCard, AuthMessage } from "../components/AuthCard";

type State = "loading" | "ok" | "error" | "missing";

/** Ziel des Links aus der Bestätigungs-Mail: /verify-email?token=... */
export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<State>(token ? "loading" : "missing");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api.verifyEmail(token)
      .then(() => { if (!cancelled) setState("ok"); })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : t("auth.verify.failed"));
        setState("error");
      });
    return () => { cancelled = true; };
  }, [token]);

  return (
    <AuthCard title={t("auth.verify.title")}>
      {state === "loading" && <AuthMessage kind="success">{t("auth.verify.loading")}</AuthMessage>}
      {state === "ok" && (
        <>
          <AuthMessage kind="success">{t("auth.verify.ok")}</AuthMessage>
          <p style={{ textAlign: "center" }}><Link to="/login" style={linkStyle}>{t("auth.toLogin")}</Link></p>
        </>
      )}
      {state === "error" && (
        <>
          <AuthMessage kind="error">{error}</AuthMessage>
          <p style={{ textAlign: "center", fontSize: 14 }}>
            {t("auth.verify.expiredHint")}{" "}
            <Link to="/login" style={linkStyle}>{t("auth.toLogin")}</Link>
          </p>
        </>
      )}
      {state === "missing" && (
        <>
          <AuthMessage kind="error">{t("auth.verify.missing")}</AuthMessage>
          <p style={{ textAlign: "center" }}><Link to="/login" style={linkStyle}>{t("auth.toLogin")}</Link></p>
        </>
      )}
    </AuthCard>
  );
}
