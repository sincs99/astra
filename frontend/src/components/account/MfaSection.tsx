import { useState } from "react";
import { t } from "../../i18n";
import { api, ApiError, type MfaSetupResult } from "../../services/api";
import { cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, ConfirmButton, ErrorState } from "../ui";
import { QrCode } from "./QrCode";
import { RecoveryCodesPanel } from "./RecoveryCodesPanel";

const TOTAL_RECOVERY_CODES = 10;

interface MfaSectionProps {
  enabled: boolean;
  /** Noch gültige Recovery-Codes (aus /auth/me); undefined, wenn das Backend sie nicht liefert */
  remaining?: number;
  onChanged: (enabled: boolean, message: string, remaining?: number) => void;
}

/** MFA/TOTP einrichten (QR-Code + Secret, Verifikation, Recovery-Codes) und deaktivieren. */
export function MfaSection({ enabled, remaining, onChanged }: MfaSectionProps) {
  const [setup, setSetup] = useState<MfaSetupResult | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [password, setPassword] = useState("");

  const run = async (fn: () => Promise<void>) => {
    try {
      setBusy(true);
      setError(null);
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("account.mfa.failed"));
    } finally {
      setBusy(false);
    }
  };

  const start = () => run(async () => setSetup(await api.setupMfa()));

  const verify = (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return setError(t("account.mfa.needCode"));
    return run(async () => {
      const result = await api.verifyMfa(code.trim());
      setRecovery(result.recovery_codes);
      setSetup(null);
      setCode("");
      onChanged(true, t("account.mfa.enabledMsg"), result.recovery_codes_remaining ?? result.recovery_codes.length);
    });
  };

  const regenerate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) return setError(t("account.mfa.regenerateNeedPw"));
    return run(async () => {
      try {
        const result = await api.regenerateRecoveryCodes(password);
        setRecovery(result.recovery_codes);
        setRegenerating(false);
        setPassword("");
        onChanged(true, t("account.mfa.regenerated"), result.recovery_codes_remaining);
      } catch (err) {
        // Falsches Passwort kommt als 403 (bewusst kein 401): die Anmeldung bleibt bestehen
        if (err instanceof ApiError && err.code === "invalid_password") throw new Error(t("account.mfa.regenerateWrongPw"));
        throw err;
      }
    });
  };

  const disable = () => run(async () => {
    await api.disableMfa();
    setRecovery(null);
    onChanged(false, t("account.mfa.disabledMsg"));
  });

  return (
    <section style={cardStyle} aria-labelledby="mfa-title">
      <h2 id="mfa-title" style={{ marginTop: 0, fontSize: 18 }}>{t("account.mfa.title")}</h2>
      {error && <ErrorState message={error} />}

      {recovery && <RecoveryCodesPanel codes={recovery} onDone={() => setRecovery(null)} />}

      {enabled && !setup && (
        <>
          <p style={{ marginTop: 0 }}>{t("account.mfa.active")}</p>
          {remaining !== undefined && !recovery && (
            remaining === 0 ? (
              <p role="alert" style={{ color: "var(--c-red)", fontWeight: 600 }}>{t("account.mfa.remainingNone")}</p>
            ) : (
              <p style={{ color: remaining <= 2 ? "var(--c-orange)" : "var(--fg-soft)", fontWeight: remaining <= 2 ? 600 : 400 }}>
                {remaining <= 2 ? t("account.mfa.remainingLow", { n: remaining }) : t("account.mfa.remaining", { n: remaining, total: TOTAL_RECOVERY_CODES })}
              </p>
            )
          )}
          {regenerating ? (
            <form onSubmit={regenerate} noValidate style={{ maxWidth: 320, marginBottom: 12 }}>
              <p style={{ margin: "0 0 8px", fontSize: 13 }}>{t("account.mfa.regenerateIntro")}</p>
              <label htmlFor="mfa-regen-pw" style={labelStyle}>{t("account.mfa.regeneratePw")}</label>
              <input id="mfa-regen-pw" type="password" autoComplete="current-password" autoFocus value={password}
                onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>{t("account.mfa.regenerateSubmit")}</button>
                <button type="button" style={btnDefault} onClick={() => { setRegenerating(false); setPassword(""); setError(null); }}>{t("account.mfa.regenerateCancel")}</button>
              </div>
            </form>
          ) : (
            <p style={{ margin: "0 0 12px" }}>
              <button type="button" style={btnDefault} onClick={() => { setRegenerating(true); setError(null); }}>{t("account.mfa.regenerate")}</button>
            </p>
          )}
          <ConfirmButton label={t("account.mfa.disable")} danger disabled={busy}
            confirmMessage={t("account.mfa.disableConfirm")}
            onConfirm={disable} />
        </>
      )}

      {!enabled && !setup && (
        <>
          <p style={{ marginTop: 0 }}>{t("account.mfa.intro")}</p>
          <button type="button" onClick={start} disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
            {t("account.mfa.setup")}
          </button>
        </>
      )}

      {setup && (
        <div>
          <p style={{ marginTop: 0 }}>
            {t("account.mfa.step1")}
          </p>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
            <QrCode value={setup.provisioning_uri} alt={t("account.mfa.qrAlt")} />
            <div>
              <div style={{ fontSize: 13, color: "var(--fg-soft)" }}>{t("account.mfa.secret")}</div>
              <code style={{ userSelect: "all", background: "var(--bg-subtle)", padding: "2px 6px", borderRadius: 4 }}>{setup.secret}</code>
            </div>
          </div>
          <form onSubmit={verify} noValidate style={{ maxWidth: 260 }}>
            <label htmlFor="mfa-code" style={labelStyle}>{t("account.mfa.step2")}</label>
            <input id="mfa-code" type="text" inputMode="numeric" autoComplete="one-time-code" value={code}
              onChange={(e) => setCode(e.target.value)} placeholder="123456" style={inputStyle} />
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>{t("account.mfa.activate")}</button>
              <button type="button" onClick={() => { setSetup(null); setCode(""); setError(null); }} style={btnDefault}>{t("account.cancel")}</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
