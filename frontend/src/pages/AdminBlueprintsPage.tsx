import { useEffect, useState } from "react";
import { api, type Blueprint, type BlueprintVariable } from "../services/api";
import {
  PageLayout, LoadingState, EmptyState, ErrorState, ConfirmButton,
  Toast, useToast,
  cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, thStyle, tdStyle,
} from "../components/ui";

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
  const [error, setError] = useState<string | null>(null);

  // Erstell-Formular
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dockerImage, setDockerImage] = useState("");
  const [startupCommand, setStartupCommand] = useState("");
  const [installScript, setInstallScript] = useState("");
  const [variables, setVariables] = useState<BlueprintVariable[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // Edit-State
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editVars, setEditVars] = useState<BlueprintVariable[]>([]);
  const [editName, setEditName] = useState("");
  const [editDockerImage, setEditDockerImage] = useState("");
  const [editStartupCommand, setEditStartupCommand] = useState("");
  const [editInstallScript, setEditInstallScript] = useState("");
  const [editSubmitting, setEditSubmitting] = useState(false);

  const loadBlueprints = async () => {
    try {
      setLoading(true);
      setError(null);
      setBlueprints(await api.getBlueprints());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
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
        variables,
      });
      setName(""); setDescription(""); setDockerImage("");
      setStartupCommand(""); setInstallScript(""); setVariables([]);
      toast.success("Blueprint erstellt.");
      await loadBlueprints();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Erstellen");
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
        variables: editVars,
      });
      setEditingId(null);
      toast.success("Blueprint aktualisiert.");
      await loadBlueprints();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Speichern");
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleDelete = async (bp: Blueprint) => {
    try {
      setError(null);
      await api.deleteBlueprint(bp.id);
      toast.success(`Blueprint "${bp.name}" gelöscht.`);
      await loadBlueprints();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Löschen");
    }
  };

  return (
    <PageLayout title="Blueprints">
      <Toast {...toast} />

      {/* ── Erstell-Formular ── */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Neuer Blueprint</h2>
        {error && <ErrorState message={error} />}
        <form onSubmit={handleSubmit}>
          <div style={grid2}>
            <Field label="Name *">
              <input type="text" value={name} onChange={e => setName(e.target.value)} required style={inputStyle} placeholder="z.B. Minecraft Vanilla" />
            </Field>
            <Field label="Docker-Image">
              <input type="text" value={dockerImage} onChange={e => setDockerImage(e.target.value)} style={inputStyle} placeholder="itzg/minecraft-server" />
            </Field>
          </div>
          <div style={grid2}>
            <Field label="Startup-Befehl">
              <input type="text" value={startupCommand} onChange={e => setStartupCommand(e.target.value)} style={inputStyle} placeholder="java -jar server.jar" />
            </Field>
            <Field label="Beschreibung">
              <input type="text" value={description} onChange={e => setDescription(e.target.value)} style={inputStyle} placeholder="Kurze Beschreibung" />
            </Field>
          </div>
          <Field label="Install-Script">
            <textarea
              value={installScript}
              onChange={e => setInstallScript(e.target.value)}
              rows={3}
              style={{ ...inputStyle, fontFamily: "monospace", fontSize: 12 }}
              placeholder={"#!/bin/bash\ncurl -o server.jar ..."}
            />
          </Field>

          <VariableEditor
            vars={variables}
            onAdd={() => addVar(variables, setVariables)}
            onRemove={idx => removeVar(variables, idx, setVariables)}
            onUpdate={(idx, field, value) => updateVar(variables, idx, field, value, setVariables)}
          />

          <div style={{ marginTop: 16 }}>
            <button type="submit" disabled={submitting} style={{ ...btnPrimary, opacity: submitting ? 0.6 : 1 }}>
              {submitting ? "Wird erstellt..." : "Blueprint erstellen"}
            </button>
          </div>
        </form>
      </div>

      {/* ── Blueprint-Liste ── */}
      {loading ? (
        <LoadingState message="Blueprints werden geladen..." />
      ) : blueprints.length === 0 ? (
        <EmptyState icon="📋" message="Noch keine Blueprints vorhanden." />
      ) : (
        blueprints.map(bp => (
          <div key={bp.id} style={cardStyle}>
            {editingId === bp.id ? (
              /* ── Edit-Modus ── */
              <div>
                <h3 style={{ marginTop: 0, fontSize: 16 }}>Blueprint bearbeiten #{bp.id}</h3>
                <div style={grid2}>
                  <Field label="Name *">
                    <input type="text" value={editName} onChange={e => setEditName(e.target.value)} style={inputStyle} />
                  </Field>
                  <Field label="Docker-Image">
                    <input type="text" value={editDockerImage} onChange={e => setEditDockerImage(e.target.value)} style={inputStyle} />
                  </Field>
                </div>
                <div style={grid2}>
                  <Field label="Startup-Befehl">
                    <input type="text" value={editStartupCommand} onChange={e => setEditStartupCommand(e.target.value)} style={inputStyle} />
                  </Field>
                </div>
                <Field label="Install-Script">
                  <textarea
                    value={editInstallScript}
                    onChange={e => setEditInstallScript(e.target.value)}
                    rows={3}
                    style={{ ...inputStyle, fontFamily: "monospace", fontSize: 12 }}
                  />
                </Field>
                <VariableEditor
                  vars={editVars}
                  onAdd={() => addVar(editVars, setEditVars)}
                  onRemove={idx => removeVar(editVars, idx, setEditVars)}
                  onUpdate={(idx, field, value) => updateVar(editVars, idx, field, value, setEditVars)}
                />
                <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                  <button
                    onClick={() => handleUpdate(bp)}
                    disabled={editSubmitting}
                    style={{ ...btnPrimary, opacity: editSubmitting ? 0.6 : 1 }}
                  >
                    {editSubmitting ? "Speichern..." : "Speichern"}
                  </button>
                  <button onClick={() => setEditingId(null)} style={btnDefault}>Abbrechen</button>
                </div>
              </div>
            ) : (
              /* ── Anzeige-Modus ── */
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <strong style={{ fontSize: 16 }}>{bp.name}</strong>
                    <span style={{ marginLeft: 8, color: "#aaa", fontSize: 12 }}>#{bp.id}</span>
                    {bp.description && <div style={{ fontSize: 13, color: "#666", marginTop: 2 }}>{bp.description}</div>}
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button onClick={() => startEdit(bp)} style={btnDefault}>✏️ Bearbeiten</button>
                    <ConfirmButton
                      label="🗑 Löschen"
                      confirmMessage={`Blueprint "${bp.name}" wirklich löschen?`}
                      onConfirm={() => handleDelete(bp)}
                      danger
                      size="sm"
                    />
                  </div>
                </div>

                <div style={{ marginTop: 8, display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: "#555" }}>
                  {bp.docker_image && <span><strong>Image:</strong> <code>{bp.docker_image}</code></span>}
                  {bp.startup_command && <span><strong>Startup:</strong> <code>{bp.startup_command}</code></span>}
                  <span><strong>Variablen:</strong> {bp.variables?.length ?? 0}</span>
                  <span style={{ color: "#aaa" }}>{bp.created_at ? new Date(bp.created_at).toLocaleString("de-CH") : "–"}</span>
                </div>

                {bp.variables && bp.variables.length > 0 && (
                  <table style={{ marginTop: 10, width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th style={{ ...thStyle, fontSize: 12 }}>Name</th>
                        <th style={{ ...thStyle, fontSize: 12 }}>ENV-Variable</th>
                        <th style={{ ...thStyle, fontSize: 12 }}>Standard</th>
                        <th style={{ ...thStyle, fontSize: 12 }}>Sichtbar</th>
                        <th style={{ ...thStyle, fontSize: 12 }}>Editierbar</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bp.variables.map((v, i) => (
                        <tr key={i}>
                          <td style={{ ...tdStyle, fontSize: 12 }}>{v.name}</td>
                          <td style={{ ...tdStyle, fontSize: 12 }}><code>{v.env_var}</code></td>
                          <td style={{ ...tdStyle, fontSize: 12 }}>{v.default_value || "–"}</td>
                          <td style={{ ...tdStyle, fontSize: 12 }}>{v.user_viewable ? "✅" : "❌"}</td>
                          <td style={{ ...tdStyle, fontSize: 12 }}>{v.user_editable ? "✅" : "❌"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        ))
      )}
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
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <strong style={{ fontSize: 13 }}>Variablen ({vars.length})</strong>
        <button type="button" onClick={onAdd} style={{ ...btnDefault, padding: "4px 12px", fontSize: 12 }}>
          + Variable
        </button>
      </div>
      {vars.map((v, i) => (
        <div key={i} style={{ border: "1px solid #e0e0e0", borderRadius: 6, padding: 10, marginBottom: 8, backgroundColor: "#fafafa" }}>
          <div style={grid3}>
            <Field label="Name">
              <input type="text" value={v.name} onChange={e => onUpdate(i, "name", e.target.value)} style={{ ...inputStyle, fontSize: 12 }} placeholder="Server Port" />
            </Field>
            <Field label="ENV-Variable">
              <input type="text" value={v.env_var} onChange={e => onUpdate(i, "env_var", e.target.value)} style={{ ...inputStyle, fontSize: 12 }} placeholder="SERVER_PORT" />
            </Field>
            <Field label="Standardwert">
              <input type="text" value={v.default_value} onChange={e => onUpdate(i, "default_value", e.target.value)} style={{ ...inputStyle, fontSize: 12 }} placeholder="25565" />
            </Field>
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ flex: 1 }}>
              <input
                type="text"
                value={v.description}
                onChange={e => onUpdate(i, "description", e.target.value)}
                style={{ ...inputStyle, fontSize: 12 }}
                placeholder="Beschreibung für den User"
              />
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, whiteSpace: "nowrap" }}>
              <input type="checkbox" checked={v.user_viewable} onChange={e => onUpdate(i, "user_viewable", e.target.checked)} />
              Sichtbar
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, whiteSpace: "nowrap" }}>
              <input type="checkbox" checked={v.user_editable} onChange={e => onUpdate(i, "user_editable", e.target.checked)} />
              Editierbar
            </label>
            <button type="button" onClick={() => onRemove(i)} style={{ ...btnDefault, padding: "4px 8px", fontSize: 12, color: "#d32f2f", borderColor: "#ef9a9a" }}>
              🗑
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Hilfs-Komponenten & Styles ──────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  );
}

const grid2: React.CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 };
const grid3: React.CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 };
