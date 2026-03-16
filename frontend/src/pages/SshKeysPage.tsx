/**
 * SSH-Keys-Verwaltung (M28).
 *
 * Erlaubt Benutzern, eigene SSH Public Keys zu verwalten:
 * - Auflisten aller Keys mit Fingerprint und Erstellungsdatum
 * - Neuen Key hinzufuegen (Name + Public Key)
 * - Key loeschen (mit Bestaetigung)
 */

import { useEffect, useState } from "react";
import { api, SshKeyEntry } from "../services/api";
import { PageLayout } from "../components/ui/PageLayout";
import { LoadingState } from "../components/ui/LoadingState";
import { ErrorState } from "../components/ui/ErrorState";
import { EmptyState } from "../components/ui/EmptyState";
import { ConfirmButton } from "../components/ui/ConfirmButton";
import { useToast, Toast } from "../components/ui/Toast";
import {
  cardStyle,
  inputStyle,
  labelStyle,
  btnPrimary,
  thStyle,
  tdStyle,
} from "../components/ui/styles";

export function SshKeysPage() {
  const toast = useToast();
  const [keys, setKeys] = useState<SshKeyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Formular-State
  const [formName, setFormName] = useState("");
  const [formKey, setFormKey] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSshKeys();
      setKeys(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Laden fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim() || !formKey.trim()) {
      toast.error("Name und Public Key sind erforderlich");
      return;
    }
    setSubmitting(true);
    try {
      await api.createSshKey({ name: formName.trim(), public_key: formKey.trim() });
      toast.success(`SSH-Key "${formName}" hinzugefuegt`);
      setFormName("");
      setFormKey("");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Fehler beim Hinzufuegen");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (key: SshKeyEntry) => {
    try {
      await api.deleteSshKey(key.id);
      toast.success(`SSH-Key "${key.name}" geloescht`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Fehler beim Loeschen");
    }
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("de-CH", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });

  const truncateKey = (key: string) => {
    const parts = key.trim().split(/\s+/);
    if (parts.length < 2) return key;
    const body = parts[1];
    return `${parts[0]} ${body.slice(0, 20)}...${body.slice(-8)}`;
  };

  return (
    <PageLayout title="SSH Keys">
      <Toast {...toast} />

      {/* Neuen Key hinzufuegen */}
      <div style={{ ...cardStyle, marginBottom: 28 }}>
        <h2 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700 }}>
          Neuen SSH-Key hinzufuegen
        </h2>
        <form onSubmit={handleAdd}>
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 2fr", marginBottom: 12 }}>
            <div>
              <label style={labelStyle}>Name</label>
              <input
                style={inputStyle}
                placeholder="z.B. MacBook Pro"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                disabled={submitting}
                maxLength={191}
              />
            </div>
            <div>
              <label style={labelStyle}>Public Key</label>
              <input
                style={inputStyle}
                placeholder="ssh-ed25519 AAAA... oder ssh-rsa AAAA..."
                value={formKey}
                onChange={(e) => setFormKey(e.target.value)}
                disabled={submitting}
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting}
            style={{ ...btnPrimary, opacity: submitting ? 0.6 : 1, cursor: submitting ? "not-allowed" : "pointer" }}
          >
            {submitting ? "Wird hinzugefuegt..." : "Key hinzufuegen"}
          </button>
        </form>
      </div>

      {/* Key-Liste */}
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : keys.length === 0 ? (
        <EmptyState message="Keine SSH-Keys vorhanden. Fuege deinen ersten Key oben hinzu." />
      ) : (
        <div style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ backgroundColor: "#fafafa" }}>
                <th style={thStyle}>Name</th>
                <th style={thStyle}>Fingerprint</th>
                <th style={thStyle}>Public Key</th>
                <th style={thStyle}>Erstellt</th>
                <th style={{ ...thStyle, textAlign: "right" }}></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id}>
                  <td style={{ ...tdStyle, fontWeight: 600 }}>{key.name}</td>
                  <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 12, color: "#555" }}>
                    {key.fingerprint}
                  </td>
                  <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11, color: "#777" }}>
                    {truncateKey(key.public_key)}
                  </td>
                  <td style={{ ...tdStyle, fontSize: 13, color: "#777", whiteSpace: "nowrap" }}>
                    {formatDate(key.created_at)}
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <ConfirmButton
                      label="Loeschen"
                      confirmMessage={`SSH-Key "${key.name}" wirklich loeschen?`}
                      onConfirm={() => handleDelete(key)}
                      danger
                      size="sm"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Info-Box */}
      <div style={{
        marginTop: 24, padding: "12px 16px",
        backgroundColor: "#e3f2fd", borderRadius: 8,
        border: "1px solid #90caf9", fontSize: 13, color: "#1565c0",
      }}>
        <strong>SFTP-Zugriff mit SSH Keys:</strong> Die hier verwalteten Keys werden fuer die
        schluesselbasierte SFTP-Authentifizierung verwendet. Unterstuetzte Formate:{" "}
        <code>ssh-ed25519</code>, <code>ssh-rsa</code>, <code>ecdsa-sha2-nistp256/384/521</code>.
        <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
          <li>Als <strong>Owner</strong> einer Instance: SFTP-Zugriff automatisch erlaubt.</li>
          <li>Als <strong>Collaborator</strong>: Berechtigung <code>file.sftp</code> erforderlich.</li>
          <li>Suspendierte Instances blockieren den SFTP-Zugriff.</li>
        </ul>
      </div>
    </PageLayout>
  );
}
