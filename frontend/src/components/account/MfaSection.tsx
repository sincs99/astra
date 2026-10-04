import { useState } from "react";
import { api, type MfaSetupResult } from "../../services/api";
import { cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, ConfirmButton, ErrorState } from "../ui";
import { QrCode } from "./QrCode";

interface MfaSectionProps {
  enabled: boolean;
  onChanged: (enabled: boolean, message: string) => void;
}

/** MFA/TOTP einrichten (QR-Code + Secret, Verifikation, Recovery-Codes) und deaktivieren. */
export function MfaSection({ enabled, onChanged }: MfaSectionProps) {
  const [setup, setSetup] = useState<MfaSetupResult | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<void>) => {
    try {
      setBusy(true);
      setError(null);
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Aktion fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const start = () => run(async () => setSetup(await api.setupMfa()));

  const verify = (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return setError("Bitte den 6-stelligen Code eingeben");
    return run(async () => {
      const result = await api.verifyMfa(code.trim());
      setRecovery(result.recovery_codes);
      setSetup(null);
      setCode("");
      onChanged(true, "MFA aktiviert.");
    });
  };

  const disable = () => run(async () => {
    await api.disableMfa();
    setRecovery(null);
    onChanged(false, "MFA deaktiviert.");
  });

  return (
    <section style={cardStyle} aria-labelledby="mfa-title">
      <h2 id="mfa-title" style={{ marginTop: 0, fontSize: 18 }}>Zwei-Faktor-Authentifizierung (MFA)</h2>
      {error && <ErrorState message={error} />}

      {recovery && (
        <div role="alert" style={{ padding: 12, marginBottom: 12, background: "var(--tint-orange)", border: "1px solid var(--border-orange)", borderRadius: 8 }}>
          <strong>Recovery-Codes – jetzt sichern!</strong>
          <p style={{ margin: "4px 0 8px", fontSize: 13 }}>
            Jeder Code funktioniert einmal, falls du keinen Zugriff auf die App hast. Sie werden nicht erneut angezeigt.
          </p>
          <code style={{ display: "block", whiteSpace: "pre-wrap", userSelect: "all" }}>{recovery.join("\n")}</code>
          <button type="button" style={{ ...btnDefault, marginTop: 8 }} onClick={() => setRecovery(null)}>
            Ich habe sie gesichert
          </button>
        </div>
      )}

      {enabled && !setup && (
        <>
          <p style={{ marginTop: 0 }}>MFA ist <strong>aktiv</strong>. Beim Login wird zusätzlich ein Code abgefragt.</p>
          <ConfirmButton label="MFA deaktivieren" danger disabled={busy}
            confirmMessage="MFA wirklich deaktivieren? Dein Konto ist danach nur noch mit dem Passwort geschützt."
            onConfirm={disable} />
        </>
      )}

      {!enabled && !setup && (
        <>
          <p style={{ marginTop: 0 }}>Schütze dein Konto mit einem Code aus einer Authenticator-App.</p>
          <button type="button" onClick={start} disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
            MFA einrichten
          </button>
        </>
      )}

      {setup && (
        <div>
          <p style={{ marginTop: 0 }}>
            1. Scanne den QR-Code mit deiner Authenticator-App (oder gib das Secret manuell ein).
          </p>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
            <QrCode value={setup.provisioning_uri} alt="QR-Code zum Einrichten der Authenticator-App" />
            <div>
              <div style={{ fontSize: 13, color: "var(--fg-soft)" }}>Secret</div>
              <code style={{ userSelect: "all", background: "var(--bg-subtle)", padding: "2px 6px", borderRadius: 4 }}>{setup.secret}</code>
            </div>
          </div>
          <form onSubmit={verify} noValidate style={{ maxWidth: 260 }}>
            <label htmlFor="mfa-code" style={labelStyle}>2. Code aus der App</label>
            <input id="mfa-code" type="text" inputMode="numeric" autoComplete="one-time-code" value={code}
              onChange={(e) => setCode(e.target.value)} placeholder="123456" style={inputStyle} />
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>Aktivieren</button>
              <button type="button" onClick={() => { setSetup(null); setCode(""); setError(null); }} style={btnDefault}>Abbrechen</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
