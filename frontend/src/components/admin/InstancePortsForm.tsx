import { useState } from "react";
import { api, type Endpoint, type Instance, type InstanceEndpoint } from "../../services/api";
import { t } from "../../i18n";
import { endpointAddress, sortedEndpoints } from "../../lib/endpoints";
import { ErrorBanner } from "./AdminField";

interface Props {
  instance: Instance;
  /** Alle Endpoints (fuer die Auswahl freier Endpoints desselben Agents) */
  endpoints: Endpoint[];
  idPrefix: string;
  /** Neuer Instanz-Stand nach einer erfolgreichen Aktion */
  onChanged: (updated: Instance, message: string) => void;
  onClose: () => void;
}

/** Ports einer Instanz verwalten: zugeordnete Endpoints (primaer setzen, entfernen) und freie Endpoints hinzufuegen. */
export function InstancePortsForm({ instance, endpoints, idPrefix, onChanged, onClose }: Props) {
  const [choice, setChoice] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const assigned = sortedEndpoints(instance);
  const free = endpoints.filter(
    (ep) => ep.agent_id === instance.agent_id && ep.instance_id === null && !ep.is_locked,
  );

  const run = async (action: () => Promise<Instance>, message: string) => {
    try {
      setBusy(true);
      setError(null);
      const updated = await action();
      onChanged(updated, message);
      setChoice("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("ainst.ports.failed"));
    } finally {
      setBusy(false);
    }
  };

  const addr = (ep: InstanceEndpoint) => endpointAddress(instance, ep);
  const selected = free.find((ep) => ep.id === choice);

  return (
    <section aria-labelledby={`${idPrefix}-title`} style={{ maxWidth: 560 }}>
      <h3 id={`${idPrefix}-title`} className="panel-title">{t("ainst.ports.title", { name: instance.name })}</h3>
      {error && <ErrorBanner message={error} />}

      <ul aria-label={t("ainst.ports.listLabel")} style={{ listStyle: "none", margin: "8px 0", padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        {assigned.map((ep) => (
          <li key={ep.id} className="kv" style={{ alignItems: "center", gap: 8 }}>
            <span>
              <span className="mono">{addr(ep)}</span>
              {ep.is_primary && <> <span className="hint">({t("ainst.ports.primary")})</span></>}
            </span>
            <span className="row-actions" style={{ marginTop: 0 }}>
              <button type="button" className="btn btn-sm" disabled={busy || ep.is_primary}
                aria-label={t("ainst.ports.setPrimaryAria", { address: addr(ep) })}
                onClick={() => run(() => api.setPrimaryInstanceEndpoint(instance.uuid, ep.id), t("ainst.ports.primarySet", { address: addr(ep) }))}>
                {t("ainst.ports.setPrimary")}
              </button>
              <span title={ep.is_primary ? t("ainst.ports.removePrimaryTip") : undefined}>
                <button type="button" className="btn btn-sm btn-danger-text" disabled={busy || ep.is_primary}
                  aria-label={t("ainst.ports.removeAria", { address: addr(ep) })}
                  onClick={() => run(() => api.removeInstanceEndpoint(instance.uuid, ep.id), t("ainst.ports.removed", { address: addr(ep) }))}>
                  {t("ainst.ports.remove")}
                </button>
              </span>
            </span>
          </li>
        ))}
      </ul>

      <div className="field">
        <label htmlFor={`${idPrefix}-add`}>{t("ainst.ports.addLabel")}</label>
        <div className="row-actions" style={{ marginTop: 0 }}>
          <select id={`${idPrefix}-add`} className="inp" value={choice} disabled={busy || free.length === 0}
            onChange={(e) => setChoice(e.target.value ? Number(e.target.value) : "")}>
            <option value="">{t("ainst.ports.choose")}</option>
            {free.map((ep) => (
              <option key={ep.id} value={ep.id}>{ep.ip}:{ep.port}{ep.auto_assign === false ? ` ${t("ainst.ports.manualSuffix")}` : ""}</option>
            ))}
          </select>
          <button type="button" className="btn btn-primary" disabled={busy || choice === ""}
            onClick={() => selected && run(
              () => api.addInstanceEndpoint(instance.uuid, selected.id),
              t("ainst.ports.added", { address: `${instance.connection?.host || selected.ip}:${selected.port}` }),
            )}>
            {t("ainst.ports.add")}
          </button>
        </div>
        {free.length === 0 && <span className="hint" role="status">{t("ainst.ports.noFree")}</span>}
      </div>

      <p className="hint">{t("ainst.ports.restartHint")}</p>
      <div className="row-actions">
        <button type="button" className="btn" onClick={onClose}>{t("ainst.ports.close")}</button>
      </div>
    </section>
  );
}
