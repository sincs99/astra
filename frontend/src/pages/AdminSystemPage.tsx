import { useEffect, useState } from "react";
import { api, type SystemVersionInfo, type UpgradeStatus, type PreflightResult } from "../services/api";
import {
  PageLayout, StatusBadge, LoadingState, ErrorState,
  cardStyle, btnDefault,
} from "../components/ui";

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
    <PageLayout title="System Info">

      {error && <ErrorState message={error} onRetry={loadData} />}
      {loading && <LoadingState message="System-Info wird geladen..." />}

      {/* Version & Build */}
      {version && (
        <div style={cardStyle}>
          <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Version & Build</h2>
          <InfoRow label="Version" value={version.version} />
          <InfoRow label="Release-Phase" value={version.release_phase} status={phaseStatus(version.release_phase)} />
          <InfoRow label="Service" value={version.service} />
          <InfoRow label="Environment" value={version.environment} status={envStatus(version.environment)} />
          <InfoRow label="Build SHA" value={version.build_sha || "n/a"} mono />
          <InfoRow label="Build Date" value={version.build_date || "n/a"} />
          <InfoRow label="Build Ref" value={version.build_ref || "n/a"} />
        </div>
      )}

      {/* Migration & Upgrade */}
      {upgrade && (
        <div style={cardStyle}>
          <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Migration & Upgrade</h2>
          <InfoRow
            label="DB Up to Date"
            value={upgrade.migration.is_up_to_date ? "Ja" : "Nein"}
            status={upgrade.migration.is_up_to_date ? "ok" : "warning"}
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
            status={upgrade.upgrade_required ? "warning" : "ok"}
          />
        </div>
      )}

      {/* Preflight */}
      {preflight && (
        <div style={cardStyle}>
          <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Preflight Check</h2>
          <InfoRow
            label="Status"
            value={preflight.overall_status}
            status={preflight.compatible ? "ok" : "error"}
          />
          {Object.entries(preflight.checks).map(([name, status]) => (
            <InfoRow key={name} label={name} value={String(status)} status={status === "ok" ? "ok" : "warning"} />
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

      <button onClick={loadData} style={btnDefault}>↻ Aktualisieren</button>
    </PageLayout>
  );
}

function InfoRow({ label, value, mono, status }: {
  label: string;
  value: string;
  mono?: boolean;
  status?: string;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: "1px solid #f0f0f0", fontSize: 14 }}>
      <span style={{ fontWeight: 600, color: "#555" }}>{label}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={mono ? { fontFamily: "monospace", fontSize: 13 } : {}}>{value}</span>
        {status && <StatusBadge status={status} size="sm" />}
      </span>
    </div>
  );
}

function envStatus(env: string): string {
  if (env === "production") return "error";
  if (env === "testing") return "info";
  return "ok";
}

function phaseStatus(phase: string): string {
  if (phase === "stable") return "ok";
  if (phase === "pilot") return "warning";
  if (phase === "rc") return "info";
  return "info";
}
