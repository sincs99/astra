import { useEffect, useState } from "react";
import {
  api,
  type SystemVersionInfo,
  type UpgradeStatus,
  type PreflightResult,
} from "../services/api";

export function AdminSystemPage() {
  const [version, setVersion] = useState<SystemVersionInfo | null>(null);
  const [upgrade, setUpgrade] = useState<UpgradeStatus | null>(null);
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [v, u] = await Promise.all([
        api.getSystemVersion(),
        api.getUpgradeStatus(),
      ]);
      setVersion(v);
      setUpgrade(u);
      // Preflight separat (kann 503 werfen)
      try {
        const p = await api.getPreflight();
        setPreflight(p);
      } catch {
        setPreflight(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1>System Info</h1>

      {error && <div style={errorStyle}>{error}</div>}
      {loading && <p>Wird geladen...</p>}

      {/* Version & Build */}
      {version && (
        <div style={cardStyle}>
          <h2 style={{ marginTop: 0 }}>Version & Build</h2>
          <InfoRow label="Version" value={version.version} />
          <InfoRow label="Service" value={version.service} />
          <InfoRow label="Environment" value={version.environment} badge={envBadge(version.environment)} />
          <InfoRow label="Build SHA" value={version.build_sha || "n/a"} mono />
          <InfoRow label="Build Date" value={version.build_date || "n/a"} />
          <InfoRow label="Build Ref" value={version.build_ref || "n/a"} />
        </div>
      )}

      {/* Migration & Upgrade */}
      {upgrade && (
        <div style={cardStyle}>
          <h2 style={{ marginTop: 0 }}>Migration & Upgrade</h2>
          <InfoRow
            label="DB Up to Date"
            value={upgrade.migration.is_up_to_date ? "Ja" : "Nein"}
            badge={upgrade.migration.is_up_to_date
              ? { text: "OK", bg: "#e8f5e9", color: "#4caf50" }
              : { text: "Upgrade noetig", bg: "#fff3e0", color: "#f57c00" }}
          />
          <InfoRow label="Code Head" value={upgrade.migration.current_head || "n/a"} mono />
          <InfoRow label="DB Revision" value={upgrade.migration.applied_revision || "n/a"} mono />
          {upgrade.migration.pending_migrations > 0 && (
            <InfoRow label="Ausstehend" value={`${upgrade.migration.pending_migrations} Migration(en)`} />
          )}
          {upgrade.migration.error && (
            <InfoRow label="Fehler" value={upgrade.migration.error} />
          )}
          <InfoRow
            label="Upgrade Required"
            value={upgrade.upgrade_required ? "Ja" : "Nein"}
          />
        </div>
      )}

      {/* Preflight */}
      {preflight && (
        <div style={cardStyle}>
          <h2 style={{ marginTop: 0 }}>Preflight Check</h2>
          <InfoRow
            label="Status"
            value={preflight.overall_status}
            badge={preflight.compatible
              ? { text: "Compatible", bg: "#e8f5e9", color: "#4caf50" }
              : { text: "Nicht kompatibel", bg: "#ffebee", color: "#d32f2f" }}
          />
          {Object.entries(preflight.checks).map(([name, status]) => (
            <InfoRow key={name} label={name} value={String(status)}
              badge={status === "ok"
                ? { text: "OK", bg: "#e8f5e9", color: "#4caf50" }
                : { text: String(status), bg: "#fff3e0", color: "#f57c00" }} />
          ))}
          {preflight.issues.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <strong style={{ fontSize: 13 }}>Probleme:</strong>
              <ul style={{ margin: "4px 0", paddingLeft: 20, fontSize: 13 }}>
                {preflight.issues.map((issue, i) => <li key={i}>{issue}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      <button onClick={loadData} style={btnStyle}>Aktualisieren</button>

      <div style={{ marginTop: 32, paddingTop: 16, borderTop: "1px solid #eee" }}>
        <a href="/" style={linkStyle}>Dashboard</a>
        <a href="/admin/jobs" style={{ ...linkStyle, marginLeft: 16 }}>Jobs</a>
        <a href="/admin/agents/monitoring" style={{ ...linkStyle, marginLeft: 16 }}>Fleet Monitoring</a>
      </div>
    </div>
  );
}

function InfoRow({ label, value, mono, badge }: {
  label: string; value: string; mono?: boolean;
  badge?: { text: string; bg: string; color: string };
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #f0f0f0", fontSize: 14 }}>
      <span style={{ fontWeight: 600, color: "#555" }}>{label}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={mono ? { fontFamily: "monospace", fontSize: 13 } : {}}>{value}</span>
        {badge && (
          <span style={{
            padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 600,
            backgroundColor: badge.bg, color: badge.color,
          }}>
            {badge.text}
          </span>
        )}
      </span>
    </div>
  );
}

function envBadge(env: string) {
  if (env === "production") return { text: "PROD", bg: "#ffebee", color: "#d32f2f" };
  if (env === "testing") return { text: "TEST", bg: "#e3f2fd", color: "#1976d2" };
  return { text: "DEV", bg: "#e8f5e9", color: "#4caf50" };
}

const cardStyle: React.CSSProperties = { border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 16 };
const btnStyle: React.CSSProperties = { padding: "8px 20px", cursor: "pointer", borderRadius: 4, border: "1px solid #ccc", backgroundColor: "#f8f8f8" };
const errorStyle: React.CSSProperties = { padding: 12, marginBottom: 16, backgroundColor: "#fee", border: "1px solid #c00", borderRadius: 4, color: "#c00" };
const linkStyle: React.CSSProperties = { color: "#1976d2", textDecoration: "none", fontWeight: 500 };
