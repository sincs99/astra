import { useState } from "react";
import { btnDanger, btnDefault, inputStyle, labelStyle, ErrorState } from "./ui";

/** Status, bei denen das Backend das Loeschen ohne `force` mit 409 ablehnt. */
export const DELETE_BLOCKING_STATUSES = ["provisioning", "reinstalling", "restoring", "transferring"];

interface DeleteInstanceFormProps {
  /** Name der Instance; muss zur Bestaetigung exakt eingegeben werden */
  name: string;
  status?: string | null;
  /** Admin: "Erzwingen" anbieten, wenn die Instance in einem laufenden Vorgang ist */
  allowForce?: boolean;
  /** Zusatzhinweis, z.B. zur laufenden Bestellung */
  notice?: string | null;
  onDelete: (force: boolean) => Promise<void>;
  onCancel: () => void;
  idPrefix?: string;
}

/** Loeschen erst nach Eingabe des Instance-Namens (ein ConfirmButton reicht hier nicht). */
export function DeleteInstanceForm({ name, status, allowForce = false, notice, onDelete, onCancel, idPrefix = "del" }: DeleteInstanceFormProps) {
  const [typed, setTyped] = useState("");
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const blocked = !!status && DELETE_BLOCKING_STATUSES.includes(status);
  const matches = typed === name;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!matches || busy) return;
    try {
      setBusy(true);
      setError(null);
      await onDelete(force);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} style={{ maxWidth: 460 }}>
      {error && <ErrorState message={error} />}
      <p style={{ marginTop: 0, fontSize: 13 }}>
        <strong>Das lässt sich nicht rückgängig machen.</strong> Alle Dateien, Backups, Datenbanken, Collaborators und
        Routinen dieser Instance werden gelöscht, die Endpoints werden freigegeben.
      </p>
      {notice && (
        <p style={{ margin: "0 0 12px", fontSize: 13, color: "#c62828", fontWeight: 600 }}>{notice}</p>
      )}
      <label htmlFor={`${idPrefix}-confirm`} style={labelStyle}>
        Zur Bestätigung den Namen <code>{name}</code> eingeben
      </label>
      <input id={`${idPrefix}-confirm`} type="text" autoComplete="off" value={typed}
        onChange={(e) => setTyped(e.target.value)} style={inputStyle} />
      {allowForce && blocked && (
        <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13, marginTop: 8 }}>
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
          Erzwingen (Status „{status}“ – laufender Vorgang wird abgebrochen)
        </label>
      )}
      {!allowForce && blocked && (
        <p style={{ fontSize: 12, color: "#c62828", margin: "8px 0 0" }}>
          Die Instance ist im Status „{status}“. Löschen ist erst danach möglich.
        </p>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button type="submit" disabled={!matches || busy || (blocked && !allowForce) || (blocked && allowForce && !force)}
          style={{ ...btnDanger, opacity: !matches || busy ? 0.5 : 1, cursor: matches && !busy ? "pointer" : "not-allowed" }}>
          {busy ? "Wird gelöscht..." : "Endgültig löschen"}
        </button>
        <button type="button" onClick={onCancel} disabled={busy} style={btnDefault}>Abbrechen</button>
      </div>
    </form>
  );
}
