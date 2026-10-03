import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../services/api";
import { linkStyle } from "../components/ui";
import { AuthCard, AuthMessage } from "../components/AuthCard";

type State = "loading" | "ok" | "error" | "missing";

/** Ziel des Links aus der Bestaetigungs-Mail: /verify-email?token=... */
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
        setError(err instanceof Error ? err.message : "Bestaetigung fehlgeschlagen");
        setState("error");
      });
    return () => { cancelled = true; };
  }, [token]);

  return (
    <AuthCard title="E-Mail bestaetigen">
      {state === "loading" && <AuthMessage kind="success">Deine Adresse wird bestaetigt...</AuthMessage>}
      {state === "ok" && (
        <>
          <AuthMessage kind="success">Deine E-Mail-Adresse wurde bestaetigt. Du kannst dich jetzt anmelden.</AuthMessage>
          <p style={{ textAlign: "center" }}><Link to="/login" style={linkStyle}>Zum Login</Link></p>
        </>
      )}
      {state === "error" && (
        <>
          <AuthMessage kind="error">{error}</AuthMessage>
          <p style={{ textAlign: "center", fontSize: 14 }}>
            Der Link kann abgelaufen sein. Melde dich an, dort kannst du eine neue Mail anfordern.{" "}
            <Link to="/login" style={linkStyle}>Zum Login</Link>
          </p>
        </>
      )}
      {state === "missing" && (
        <>
          <AuthMessage kind="error">Der Link ist unvollstaendig (Token fehlt).</AuthMessage>
          <p style={{ textAlign: "center" }}><Link to="/login" style={linkStyle}>Zum Login</Link></p>
        </>
      )}
    </AuthCard>
  );
}
