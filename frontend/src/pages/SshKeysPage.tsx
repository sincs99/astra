/**
 * SSH-Keys-Verwaltung (M28).
 *
 * Erlaubt Benutzern, eigene SSH Public Keys zu verwalten:
 * - Auflisten aller Keys mit Fingerprint und Erstellungsdatum
 * - Neuen Key hinzufügen (Name + Public Key)
 * - Key löschen (mit Bestätigung)
 */

import { useEffect, useState } from "react";
import { t } from "../i18n";
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
import { formatDateLong } from "../lib/dates";

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
      setError(e instanceof Error ? e.message : t("ssh.loadFailed"));
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
      toast.error(t("ssh.required"));
      return;
    }
    setSubmitting(true);
    try {
      await api.createSshKey({ name: formName.trim(), public_key: formKey.trim() });
      toast.success(t("ssh.added", { name: formName }));
      setFormName("");
      setFormKey("");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t("ssh.addFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (key: SshKeyEntry) => {
    try {
      await api.deleteSshKey(key.id);
      toast.success(t("ssh.deleted", { name: key.name }));
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : t("ssh.deleteFailed"));
    }
  };

  const formatDate = formatDateLong;

  const truncateKey = (key: string) => {
    const parts = key.trim().split(/\s+/);
    if (parts.length < 2) return key;
    const body = parts[1];
    return `${parts[0]} ${body.slice(0, 20)}...${body.slice(-8)}`;
  };

  return (
    <PageLayout title={t("ssh.title")}>
      <Toast {...toast} />

      {/* Neuen Key hinzufügen */}
      <div style={{ ...cardStyle, marginBottom: 28 }}>
        <h2 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700 }}>
          {t("ssh.addTitle")}
        </h2>
        <form onSubmit={handleAdd}>
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 2fr", marginBottom: 12 }}>
            <div>
              <label htmlFor="ssh-name" style={labelStyle}>{t("ssh.name")}</label>
              <input
                id="ssh-name"
                style={inputStyle}
                placeholder={t("ssh.namePh")}
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                disabled={submitting}
                maxLength={191}
              />
            </div>
            <div>
              <label htmlFor="ssh-key" style={labelStyle}>{t("ssh.publicKey")}</label>
              <input
                id="ssh-key"
                style={inputStyle}
                placeholder={t("ssh.keyPh")}
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
            {submitting ? t("ssh.adding") : t("ssh.add")}
          </button>
        </form>
      </div>

      {/* Key-Liste */}
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : keys.length === 0 ? (
        <EmptyState message={t("ssh.none")} />
      ) : (
        <div style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ backgroundColor: "var(--bg)" }}>
                <th style={thStyle}>{t("ssh.name")}</th>
                <th style={thStyle}>{t("ssh.fingerprint")}</th>
                <th style={thStyle}>{t("ssh.publicKey")}</th>
                <th style={thStyle}>{t("ssh.created")}</th>
                <th style={{ ...thStyle, textAlign: "right" }}><span style={{ position: "absolute", left: -9999 }}>{t("ssh.actions")}</span></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id}>
                  <td style={{ ...tdStyle, fontWeight: 600 }}>{key.name}</td>
                  <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 12, color: "var(--text-2)" }}>
                    {key.fingerprint}
                  </td>
                  <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11, color: "var(--text-3)" }}>
                    {truncateKey(key.public_key)}
                  </td>
                  <td style={{ ...tdStyle, fontSize: 13, color: "var(--text-3)", whiteSpace: "nowrap" }}>
                    {formatDate(key.created_at)}
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <ConfirmButton
                      label={t("ssh.delete")}
                      confirmMessage={t("ssh.deleteConfirm", { name: key.name })}
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
        backgroundColor: "var(--accent-soft)", borderRadius: 8,
        border: "1px solid color-mix(in srgb, var(--accent) 35%, transparent)", fontSize: 13, color: "var(--accent)",
      }}>
        <strong>{t("ssh.infoTitle")}</strong> {t("ssh.infoText")}{" "}
        <code>ssh-ed25519</code>, <code>ssh-rsa</code>, <code>ecdsa-sha2-nistp256/384/521</code>.
        <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
          <li>{t("ssh.infoOwner")}</li>
          <li>{t("ssh.infoCollab")}</li>
          <li>{t("ssh.infoSuspended")}</li>
        </ul>
      </div>
    </PageLayout>
  );
}
