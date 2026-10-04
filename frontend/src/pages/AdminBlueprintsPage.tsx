import { useEffect, useState } from "react";
import { api, type Blueprint, type BlueprintVariable } from "../services/api";
import { BlueprintImport } from "../components/BlueprintImport";
import { PageLayout, ConfirmButton, Toast, useToast, ScrollRegion } from "../components/ui";
import { Icon } from "../components/ui/Icon";
import { Field, ErrorBanner, fieldGrid } from "../components/admin/AdminField";
import { formatDateTime } from "../lib/dates";
import { t } from "../i18n";

const EMPTY_VAR: BlueprintVariable = {
  name: "",
  description: "",
  env_var: "",
  default_value: "",
  user_viewable: true,
  user_editable: true,
};

export function AdminBlueprintsPage() {
  const toast = useToast();
  const [blueprints, setBlueprints] = useState<Blueprint[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Erstell-Formular
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dockerImage, setDockerImage] = useState("");
  const [startupCommand, setStartupCommand] = useState("");
  const [installScript, setInstallScript] = useState("");
  const [installContainer, setInstallContainer] = useState("");
  const [configStop, setConfigStop] = useState("");
  const [startupDone, setStartupDone] = useState("");
  const [fileDenylist, setFileDenylist] = useState("");
  const [variables, setVariables] = useState<BlueprintVariable[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // Edit-State
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editVars, setEditVars] = useState<BlueprintVariable[]>([]);
  const [editName, setEditName] = useState("");
  const [editDockerImage, setEditDockerImage] = useState("");
  const [editStartupCommand, setEditStartupCommand] = useState("");
  const [editInstallScript, setEditInstallScript] = useState("");
  const [editInstallContainer, setEditInstallContainer] = useState("");
  const [editConfigStop, setEditConfigStop] = useState("");
  const [editStartupDone, setEditStartupDone] = useState("");
  const [editFileDenylist, setEditFileDenylist] = useState("");
  const [editSubmitting, setEditSubmitting] = useState(false);

  // Wings-Prozessfelder (M33): Textzeilen <-> Listen
  const toLines = (list: string[] | null | undefined) => (list ?? []).join("\n");
  const fromLines = (text: string) => text.split("\n").map(l => l.trim()).filter(Boolean);

  const loadBlueprints = async () => {
    try {
      setLoading(true);
      setLoadError(null);
      setBlueprints(await api.getBlueprints());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : t("ainst.bp.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadBlueprints(); }, []);

  // ── Variable-Hilfsfunktionen ────────────────────────

  const addVar = (vars: BlueprintVariable[], set: (v: BlueprintVariable[]) => void) =>
    set([...vars, { ...EMPTY_VAR }]);

  const removeVar = (vars: BlueprintVariable[], idx: number, set: (v: BlueprintVariable[]) => void) =>
    set(vars.filter((_, i) => i !== idx));

  const updateVar = (
    vars: BlueprintVariable[],
    idx: number,
    field: keyof BlueprintVariable,
    value: string | boolean,
    set: (v: BlueprintVariable[]) => void,
  ) => {
    const updated = [...vars];
    updated[idx] = { ...updated[idx], [field]: value };
    set(updated);
  };

  // ── Erstellen ───────────────────────────────────────

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      setSubmitting(true);
      setError(null);
      await api.createBlueprint({
        name: name.trim(),
        description: description.trim() || undefined,
        docker_image: dockerImage.trim() || undefined,
        startup_command: startupCommand.trim() || undefined,
        install_script: installScript.trim() || undefined,
        install_container: installContainer.trim() || undefined,
        config_stop: configStop.trim() || undefined,
        config_startup: startupDone.trim() ? { done: fromLines(startupDone) } : undefined,
        file_denylist: fileDenylist.trim() ? fromLines(fileDenylist) : undefined,
        variables,
      });
      setName(""); setDescription(""); setDockerImage("");
      setStartupCommand(""); setInstallScript(""); setVariables([]);
      setInstallContainer(""); setConfigStop(""); setStartupDone(""); setFileDenylist("");
      toast.success(t("ainst.bp.created"));
      await loadBlueprints();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("ainst.bp.createFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  // ── Bearbeiten ──────────────────────────────────────

  const startEdit = (bp: Blueprint) => {
    setEditingId(bp.id);
    setEditName(bp.name);
    setEditDockerImage(bp.docker_image ?? "");
    setEditStartupCommand(bp.startup_command ?? "");
    setEditInstallScript(bp.install_script ?? "");
    setEditInstallContainer(bp.install_container ?? "");
    setEditConfigStop(bp.config_stop ?? "");
    setEditStartupDone(toLines(bp.config_startup?.done));
    setEditFileDenylist(toLines(bp.file_denylist));
    setEditVars(bp.variables ? [...bp.variables] : []);
  };

  const handleUpdate = async (bp: Blueprint) => {
    try {
      setEditSubmitting(true);
      setError(null);
      await api.updateBlueprint(bp.id, {
        name: editName.trim(),
        docker_image: editDockerImage.trim() || undefined,
        startup_command: editStartupCommand.trim() || undefined,
        install_script: editInstallScript.trim() || undefined,
        install_container: editInstallContainer.trim() || undefined,
        config_stop: editConfigStop.trim() || undefined,
        config_startup: { done: fromLines(editStartupDone) },
        file_denylist: fromLines(editFileDenylist),
        variables: editVars,
      });
      setEditingId(null);
      toast.success(t("ainst.bp.updated"));
      await loadBlueprints();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("ainst.bp.saveFailed"));
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleDelete = async (bp: Blueprint) => {
    try {
      setError(null);
      await api.deleteBlueprint(bp.id);
      toast.success(t("ainst.bp.deleted", { name: bp.name }));
      await loadBlueprints();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("ainst.bp.deleteFailed"));
    }
  };

  const col = {
    name: t("ainst.bp.colName"), env: t("ainst.bp.colEnv"), def: t("ainst.bp.colDefault"),
    viewable: t("ainst.bp.colViewable"), editable: t("ainst.bp.colEditable"),
  };
  const yesNo = (v: boolean) => (v ? t("ainst.yes") : t("ainst.no"));

  return (
    <PageLayout title={t("ainst.bp.title")}>
      <Toast {...toast} />
      <div className="stack">

        {error && <ErrorBanner message={error} />}

        {/* ── Import (Pterodactyl-Egg) ── */}
        <BlueprintImport
          onImported={(bp) => { toast.success(t("ainst.bp.imported", { name: bp.name })); loadBlueprints(); }}
          onError={() => { /* Fehler wird im Import-Formular angezeigt */ }}
        />

        {/* ── Erstell-Formular ── */}
        <section className="panel" aria-labelledby="bp-new-title">
          <div className="panel-head"><h2 id="bp-new-title">{t("ainst.bp.newTitle")}</h2></div>
          <form className="panel-body" onSubmit={handleSubmit}>
            <p className="hint">{t("ainst.required")}</p>
            <div style={fieldGrid(240)}>
              <Field label={t("ainst.bp.name")}>
                <input className="inp" type="text" value={name} onChange={e => setName(e.target.value)} required aria-required="true" placeholder={t("ainst.bp.namePh")} />
              </Field>
              <Field label={t("ainst.bp.dockerImage")}>
                <input className="inp mono" type="text" value={dockerImage} onChange={e => setDockerImage(e.target.value)} placeholder="itzg/minecraft-server" />
              </Field>
              <Field label={t("ainst.bp.startupCommand")}>
                <input className="inp mono" type="text" value={startupCommand} onChange={e => setStartupCommand(e.target.value)} placeholder="java -jar server.jar" />
              </Field>
              <Field label={t("ainst.bp.description")}>
                <input className="inp" type="text" value={description} onChange={e => setDescription(e.target.value)} placeholder={t("ainst.bp.descriptionPh")} />
              </Field>
            </div>
            <Field label={t("ainst.bp.installScript")}>
              <textarea className="inp mono" value={installScript} onChange={e => setInstallScript(e.target.value)} rows={3}
                style={{ padding: "8px 12px", resize: "vertical" }} placeholder={"#!/bin/bash\ncurl -o server.jar ..."} />
            </Field>
            <WingsProcessFields
              installContainer={installContainer} onInstallContainer={setInstallContainer}
              configStop={configStop} onConfigStop={setConfigStop}
              startupDone={startupDone} onStartupDone={setStartupDone}
              fileDenylist={fileDenylist} onFileDenylist={setFileDenylist}
            />
            <VariableEditor
              vars={variables}
              onAdd={() => addVar(variables, setVariables)}
              onRemove={idx => removeVar(variables, idx, setVariables)}
              onUpdate={(idx, field, value) => updateVar(variables, idx, field, value, setVariables)}
            />
            <div className="row-actions">
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? t("ainst.bp.creating") : t("ainst.bp.create")}
              </button>
            </div>
          </form>
        </section>

        {/* ── Blueprint-Liste ── */}
        <h2 className="section-title" style={{ margin: 0 }}>{t("ainst.bp.listTitle")}</h2>
        {loadError && <ErrorBanner message={loadError} title={t("ainst.errorTitle")} retryLabel={t("ainst.retry")} onRetry={loadBlueprints} />}
        {loading ? (
          <p className="hint" role="status" aria-busy="true">{t("ainst.bp.loading")}</p>
        ) : blueprints.length === 0 ? (
          !loadError && <p className="hint">{t("ainst.bp.empty")}</p>
        ) : (
          blueprints.map(bp => (
            <section key={bp.id} className="panel" aria-labelledby={`bp-title-${bp.id}`}>
              {editingId === bp.id ? (
                /* ── Edit-Modus ── */
                <>
                  <div className="panel-head"><h2 id={`bp-title-${bp.id}`}>{t("ainst.bp.editTitle", { id: bp.id })}</h2></div>
                  <form className="panel-body" onSubmit={e => { e.preventDefault(); handleUpdate(bp); }}>
                    <p className="hint">{t("ainst.required")}</p>
                    <div style={fieldGrid(240)}>
                      <Field label={t("ainst.bp.name")}>
                        <input className="inp" type="text" value={editName} onChange={e => setEditName(e.target.value)} required aria-required="true" />
                      </Field>
                      <Field label={t("ainst.bp.dockerImage")}>
                        <input className="inp mono" type="text" value={editDockerImage} onChange={e => setEditDockerImage(e.target.value)} />
                      </Field>
                      <Field label={t("ainst.bp.startupCommand")}>
                        <input className="inp mono" type="text" value={editStartupCommand} onChange={e => setEditStartupCommand(e.target.value)} />
                      </Field>
                    </div>
                    <Field label={t("ainst.bp.installScript")}>
                      <textarea className="inp mono" value={editInstallScript} onChange={e => setEditInstallScript(e.target.value)} rows={3}
                        style={{ padding: "8px 12px", resize: "vertical" }} />
                    </Field>
                    <WingsProcessFields
                      installContainer={editInstallContainer} onInstallContainer={setEditInstallContainer}
                      configStop={editConfigStop} onConfigStop={setEditConfigStop}
                      startupDone={editStartupDone} onStartupDone={setEditStartupDone}
                      fileDenylist={editFileDenylist} onFileDenylist={setEditFileDenylist}
                    />
                    <VariableEditor
                      vars={editVars}
                      onAdd={() => addVar(editVars, setEditVars)}
                      onRemove={idx => removeVar(editVars, idx, setEditVars)}
                      onUpdate={(idx, field, value) => updateVar(editVars, idx, field, value, setEditVars)}
                    />
                    <div className="row-actions">
                      <button type="submit" className="btn btn-primary" disabled={editSubmitting}>
                        {editSubmitting ? t("ainst.bp.saving") : t("ainst.bp.save")}
                      </button>
                      <button type="button" className="btn" onClick={() => setEditingId(null)}>{t("ainst.bp.cancel")}</button>
                    </div>
                  </form>
                </>
              ) : (
                /* ── Anzeige-Modus ── */
                <>
                  <div className="panel-head">
                    <h2 id={`bp-title-${bp.id}`}>{bp.name} <span className="mono hint">#{bp.id}</span></h2>
                    <div className="row-actions" style={{ marginTop: 0 }}>
                      <button type="button" className="btn btn-sm" onClick={() => startEdit(bp)}>
                        <Icon name="pencil" size={14} />{t("ainst.bp.edit")}
                      </button>
                      <ConfirmButton
                        label={t("ainst.bp.delete")}
                        confirmMessage={t("ainst.bp.confirmDelete", { name: bp.name })}
                        onConfirm={() => handleDelete(bp)}
                        danger
                        size="sm"
                      />
                    </div>
                  </div>
                  <div className="panel-body">
                    {bp.description && <p className="hint" style={{ color: "var(--text-2)" }}>{bp.description}</p>}
                    <div className="kv-list">
                      {bp.docker_image && <div className="kv"><span>{t("ainst.bp.image")}</span><span className="mono">{bp.docker_image}</span></div>}
                      {bp.startup_command && <div className="kv"><span>{t("ainst.bp.startup")}</span><span className="mono">{bp.startup_command}</span></div>}
                      <div className="kv"><span>{t("ainst.bp.stop")}</span><span className="mono">{bp.config_stop || "stop"}</span></div>
                      <div className="kv">
                        <span>{t("ainst.bp.startupDetect")}</span>
                        {bp.config_startup?.done?.length
                          ? <span className="mono">{bp.config_startup.done.join(" | ")}</span>
                          : <span className="text-danger">{t("ainst.bp.startupDetectMissing")}</span>}
                      </div>
                      <div className="kv"><span>{t("ainst.bp.variablesCount")}</span><span className="mono">{bp.variables?.length ?? 0}</span></div>
                      <div className="kv"><span>{t("ainst.bp.created_at")}</span><span>{formatDateTime(bp.created_at)}</span></div>
                    </div>

                    {bp.variables && bp.variables.length > 0 && (
                      <ScrollRegion label={t("ainst.bp.varsTableLabel", { name: bp.name })}>
                        <table className="tbl tbl-cards">
                          <thead>
                            <tr>
                              <th scope="col">{col.name}</th>
                              <th scope="col">{col.env}</th>
                              <th scope="col">{col.def}</th>
                              <th scope="col">{col.viewable}</th>
                              <th scope="col">{col.editable}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {bp.variables.map((v, i) => (
                              <tr key={i}>
                                <td data-label={col.name}>{v.name}</td>
                                <td data-label={col.env}><span className="mono">{v.env_var}</span></td>
                                <td data-label={col.def}>{v.default_value || t("ainst.none")}</td>
                                <td data-label={col.viewable}>{yesNo(v.user_viewable)}</td>
                                <td data-label={col.editable}>{yesNo(v.user_editable)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </ScrollRegion>
                    )}
                  </div>
                </>
              )}
            </section>
          ))
        )}
      </div>
    </PageLayout>
  );
}

// ── Variablen-Editor-Komponente ─────────────────────────

function VariableEditor({
  vars,
  onAdd,
  onRemove,
  onUpdate,
}: {
  vars: BlueprintVariable[];
  onAdd: () => void;
  onRemove: (idx: number) => void;
  onUpdate: (idx: number, field: keyof BlueprintVariable, value: string | boolean) => void;
}) {
  return (
    <fieldset className="fieldset">
      <legend className="panel-title" style={{ padding: 0 }}>{t("ainst.bp.variables", { n: vars.length })}</legend>
      <div className="row-actions" style={{ marginTop: 0 }}>
        <button type="button" className="btn btn-sm" onClick={onAdd}>
          <Icon name="plus" size={14} />{t("ainst.bp.addVar")}
        </button>
      </div>
      {vars.map((v, i) => (
        <div key={i} className="stack" style={{ gap: 12, border: "1px solid var(--border)", borderRadius: "var(--radius-card)", padding: 12, background: "var(--surface-2)" }}>
          <div style={fieldGrid(160)}>
            <Field label={t("ainst.bp.varName")}>
              <input className="inp" type="text" value={v.name} onChange={e => onUpdate(i, "name", e.target.value)} placeholder="Server Port" />
            </Field>
            <Field label={t("ainst.bp.varEnv")}>
              <input className="inp mono" type="text" value={v.env_var} onChange={e => onUpdate(i, "env_var", e.target.value)} placeholder="SERVER_PORT" />
            </Field>
            <Field label={t("ainst.bp.varDefault")}>
              <input className="inp mono" type="text" value={v.default_value} onChange={e => onUpdate(i, "default_value", e.target.value)} placeholder="25565" />
            </Field>
          </div>
          <div className="row-actions" style={{ marginTop: 0 }}>
            <div style={{ flex: "1 1 220px" }}>
              <input className="inp" type="text" value={v.description} onChange={e => onUpdate(i, "description", e.target.value)}
                aria-label={`${t("ainst.bp.varDescription")} (${i + 1})`} placeholder={t("ainst.bp.varDescription")} />
            </div>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "var(--fs-small)", whiteSpace: "nowrap" }}>
              <input type="checkbox" checked={v.user_viewable} onChange={e => onUpdate(i, "user_viewable", e.target.checked)} />
              {t("ainst.bp.varViewable")}
            </label>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "var(--fs-small)", whiteSpace: "nowrap" }}>
              <input type="checkbox" checked={v.user_editable} onChange={e => onUpdate(i, "user_editable", e.target.checked)} />
              {t("ainst.bp.varEditable")}
            </label>
            <button type="button" className="btn btn-sm btn-icon btn-danger-text" onClick={() => onRemove(i)}
              aria-label={t("ainst.bp.removeVar", { n: i + 1 })} title={t("ainst.bp.removeVar", { n: i + 1 })}>
              <Icon name="trash" size={14} />
            </button>
          </div>
        </div>
      ))}
    </fieldset>
  );
}

// ── Wings-Prozessfelder (M33) ───────────────────────────

function WingsProcessFields({
  installContainer, onInstallContainer,
  configStop, onConfigStop,
  startupDone, onStartupDone,
  fileDenylist, onFileDenylist,
}: {
  installContainer: string; onInstallContainer: (v: string) => void;
  configStop: string; onConfigStop: (v: string) => void;
  startupDone: string; onStartupDone: (v: string) => void;
  fileDenylist: string; onFileDenylist: (v: string) => void;
}) {
  return (
    <fieldset className="fieldset">
      <legend className="panel-title">{t("ainst.bp.wingsTitle")}</legend>
      <div style={fieldGrid(240)}>
        <Field label={t("ainst.bp.installContainer")}>
          <input className="inp mono" type="text" value={installContainer} onChange={e => onInstallContainer(e.target.value)}
            placeholder="ghcr.io/pterodactyl/installers:debian" />
        </Field>
        <Field label={t("ainst.bp.configStop")}>
          <input className="inp mono" type="text" value={configStop} onChange={e => onConfigStop(e.target.value)} placeholder="stop" />
        </Field>
        <Field label={t("ainst.bp.startupDone")}>
          <textarea className="inp mono" value={startupDone} onChange={e => onStartupDone(e.target.value)} rows={2}
            style={{ padding: "8px 12px", resize: "vertical" }} placeholder={")! For help, type "} />
        </Field>
        <Field label={t("ainst.bp.fileDenylist")}>
          <textarea className="inp mono" value={fileDenylist} onChange={e => onFileDenylist(e.target.value)} rows={2}
            style={{ padding: "8px 12px", resize: "vertical" }} placeholder={"*.jar"} />
        </Field>
      </div>
    </fieldset>
  );
}
