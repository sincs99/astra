import { useEffect, useState } from "react";
import { api, type Agent } from "../services/api";
import { formatDateTime } from "../lib/dates";
import { btnDanger, btnDefault, inputStyle, labelStyle, ErrorState } from "./ui";

type BackupCheck =
  | { state: "loading" }
  | { state: "ok"; lastAt: string | null }
  | { state: "none" }
  | { state: "unknown" };

interface TransferInstanceFormProps {
  instanceUuid: string;
  instanceName: string;
  /** Moegliche Ziele (aktiv, nicht der aktuelle Agent) */
  agents: Agent[];
  onTransfer: (targetAgentId: number) => Promise<void>;
  onCancel: () => void;
  idPrefix?: string;
}

/**
 * Transfer auf einen anderen Agent: Die Instance wird auf dem Ziel NEU angelegt, Dateien werden nicht
 * uebertragen. Deshalb: Warnung, Backup-Bestaetigung und Namenseingabe (wie beim Loeschen).
 */
export function TransferInstanceForm({ instanceUuid, instanceName, agents, onTransfer, onCancel, idPrefix = "transfer" }: TransferInstanceFormProps) {
  const [target, setTarget] = useState<number | "">("");
  const [hasBackup, setHasBackup] = useState(false);
  const [typed, setTyped] = useState("");
  const [check, setCheck] = useState<BackupCheck>({ state: "loading" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Admin-Endpunkt mit Anzahl und Zeitpunkt des letzten erfolgreichen Backups; bei Fehler gilt nur die Checkbox
  useEffect(() => {
    let cancelled = false;
    api.getAdminInstanceBackups(instanceUuid)
      .then((info) => {
        if (cancelled) return;
        setCheck(info.successful_count > 0 ? { state: "ok", lastAt: info.last_successful_backup_at } : { state: "none" });
      })
      .catch(() => { if (!cancelled) setCheck({ state: "unknown" }); });
    return () => { cancelled = true; };
  }, [instanceUuid]);

  const ready =
    target !== "" && hasBackup && typed === instanceName && check.state !== "none" && check.state !== "loading";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready || busy) return;
    try {
      setBusy(true);
      setError(null);
      await onTransfer(target as number);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transfer fehlgeschlagen");
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} style={{ maxWidth: 520 }}>
      {error && <ErrorState message={error} />}
      <div role="alert" style={{ padding: "10px 14px", marginBottom: 12, backgroundColor: "var(--tint-red)", border: "1px solid var(--border-red)", borderRadius: 8, color: "var(--c-red)", fontSize: 13, fontWeight: 600 }}>
        Achtung: Beim Transfer werden die Serverdaten NICHT übertragen. Vorher ein Backup erstellen und danach wiederherstellen.
      </div>

      <div style={{ fontSize: 13, marginBottom: 12 }} role="status">
        {check.state === "loading" && <span style={{ color: "var(--fg-muted)" }}>Backups werden geprüft…</span>}
        {check.state === "ok" && (
          <span style={{ color: "var(--c-green)" }}>Letztes erfolgreiches Backup: {formatDateTime(check.lastAt)}</span>
        )}
        {check.state === "none" && (
          <span style={{ color: "var(--c-red)", fontWeight: 600 }}>
            Für diese Instance gibt es kein erfolgreiches Backup. Erstelle zuerst eines, sonst gehen die Daten verloren.
          </span>
        )}
        {check.state === "unknown" && (
          <span style={{ color: "var(--fg-muted)" }}>Die Backups konnten nicht geprüft werden. Bitte stelle selbst sicher, dass ein aktuelles Backup existiert.</span>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <label htmlFor={`${idPrefix}-target`} style={labelStyle}>Ziel-Agent</label>
        <select id={`${idPrefix}-target`} value={target} style={inputStyle}
          onChange={(e) => setTarget(e.target.value ? Number(e.target.value) : "")}>
          <option value="">– Ziel-Agent wählen –</option>
          {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>

      <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13, marginBottom: 12 }}>
        <input type="checkbox" checked={hasBackup} onChange={(e) => setHasBackup(e.target.checked)} style={{ marginTop: 2 }} />
        <span>Ich habe ein aktuelles Backup</span>
      </label>

      <label htmlFor={`${idPrefix}-confirm`} style={labelStyle}>
        Zur Bestätigung den Namen <code>{instanceName}</code> eingeben
      </label>
      <input id={`${idPrefix}-confirm`} type="text" autoComplete="off" value={typed}
        onChange={(e) => setTyped(e.target.value)} style={inputStyle} />

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button type="submit" disabled={!ready || busy}
          style={{ ...btnDanger, opacity: !ready || busy ? 0.5 : 1, cursor: ready && !busy ? "pointer" : "not-allowed" }}>
          {busy ? "Wird gestartet…" : "Transfer starten"}
        </button>
        <button type="button" onClick={onCancel} disabled={busy} style={btnDefault}>Abbrechen</button>
      </div>
    </form>
  );
}
