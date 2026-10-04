import { useEffect, useState } from "react";
import { api, type SystemVersionInfo, type UpgradeStatus, type PreflightResult } from "../services/api";
import { BillingTickCard } from "../components/BillingTickCard";
import { PageLayout, StatusBadge } from "../components/ui";
import { hasKey, t } from "../i18n";

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
      setError(err instanceof Error ? err.message : t("asys.system.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const na = t("asys.system.na");
  const yesNo = (b: boolean) => (b ? t("asys.system.yes") : t("asys.system.no"));

  const refreshButton = (
    <button type="button" className="btn btn-sm" onClick={loadData}>{t("asys.system.refresh")}</button>
  );

  return (
    <PageLayout title={t("asys.system.title")} actions={refreshButton}>
      <div className="stack">
        {error && (
          <div className="banner banner-danger" role="alert">
            <span className="dot dot-danger" aria-hidden="true" />
            <span className="banner-text">{error}</span>
            <button type="button" className="btn btn-sm" onClick={loadData}>{t("common.retry")}</button>
          </div>
        )}
        {loading && <p className="hint" role="status" aria-busy="true">{t("asys.system.loading")}</p>}

        <BillingTickCard />

        <div className="cols">
          {version && (
            <section className="panel">
              <div className="panel-head"><h2>{t("asys.system.versionTitle")}</h2></div>
              <div className="panel-body kv-list">
                <InfoRow label={t("asys.system.version")} value={version.version} />
                <InfoRow label={t("asys.system.phase")} value={version.release_phase} status={phaseStatus(version.release_phase)} />
                <InfoRow label={t("asys.system.service")} value={version.service} />
                <InfoRow label={t("asys.system.environment")} value={version.environment} status={envStatus(version.environment)} />
                <InfoRow label={t("asys.system.buildSha")} value={version.build_sha || na} mono />
                <InfoRow label={t("asys.system.buildDate")} value={version.build_date || na} />
                <InfoRow label={t("asys.system.buildRef")} value={version.build_ref || na} />
              </div>
            </section>
          )}

          {upgrade && (
            <section className="panel">
              <div className="panel-head"><h2>{t("asys.system.migrationTitle")}</h2></div>
              <div className="panel-body kv-list">
                <InfoRow
                  label={t("asys.system.dbUpToDate")}
                  value={yesNo(upgrade.migration.is_up_to_date)}
                  status={upgrade.migration.is_up_to_date ? "ok" : "warning"}
                />
                <InfoRow label={t("asys.system.codeHead")} value={upgrade.migration.current_head || na} mono />
                <InfoRow label={t("asys.system.dbRevision")} value={upgrade.migration.applied_revision || na} mono />
                {upgrade.migration.pending_migrations > 0 && (
                  <InfoRow label={t("asys.system.pending")} value={t("asys.system.pendingCount", { n: upgrade.migration.pending_migrations })} />
                )}
                {upgrade.migration.error && (
                  <InfoRow label={t("asys.system.error")} value={upgrade.migration.error} />
                )}
                <InfoRow
                  label={t("asys.system.upgradeRequired")}
                  value={yesNo(upgrade.upgrade_required)}
                  status={upgrade.upgrade_required ? "warning" : "ok"}
                />
              </div>
            </section>
          )}

          {preflight && (
            <section className="panel">
              <div className="panel-head"><h2>{t("asys.system.preflightTitle")}</h2></div>
              <div className="panel-body kv-list">
                <InfoRow
                  label={t("asys.system.status")}
                  value={preflight.overall_status}
                  status={preflight.compatible ? "ok" : "error"}
                />
                {Object.entries(preflight.checks).map(([name, status]) => (
                  <InfoRow key={name} label={name} value={String(status)} status={status === "ok" ? "ok" : "warning"} />
                ))}
                {preflight.issues.length > 0 && (
                  <div>
                    <strong>{t("asys.system.issues")}</strong>
                    <ul style={{ margin: "4px 0", paddingLeft: 20 }}>
                      {preflight.issues.map((issue, i) => <li key={i}>{issue}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </PageLayout>
  );
}

function badgeLabel(status: string): string | undefined {
  const key = `asys.system.lbl.${status}`;
  return hasKey(key) ? t(key) : undefined;
}

function InfoRow({ label, value, mono, status }: {
  label: string;
  value: string;
  mono?: boolean;
  status?: string;
}) {
  return (
    <div className="kv">
      <span>{label}</span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }}>
        <span className={mono ? "mono" : undefined}>{value}</span>
        {status && <StatusBadge status={status} label={badgeLabel(status)} size="sm" />}
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
  return "info";
}
