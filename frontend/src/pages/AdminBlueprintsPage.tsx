import { useEffect, useState } from "react";
import { api, type Blueprint } from "../services/api";

export function AdminBlueprintsPage() {
  const [blueprints, setBlueprints] = useState<Blueprint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Formular-State
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dockerImage, setDockerImage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadBlueprints = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getBlueprints();
      setBlueprints(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBlueprints();
  }, []);

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
      });
      setName("");
      setDescription("");
      setDockerImage("");
      await loadBlueprints();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Erstellen");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 24 }}>
      <h1>Blueprints</h1>

      {/* Erstell-Formular */}
      <div
        style={{
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          marginBottom: 24,
        }}
      >
        <h2 style={{ marginTop: 0 }}>Neuer Blueprint</h2>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>
              Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="z.B. Minecraft Vanilla"
              required
              style={{ width: "100%", padding: 8, boxSizing: "border-box" }}
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>
              Beschreibung
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Kurze Beschreibung des Blueprints"
              rows={3}
              style={{ width: "100%", padding: 8, boxSizing: "border-box" }}
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>
              Docker-Image
            </label>
            <input
              type="text"
              value={dockerImage}
              onChange={(e) => setDockerImage(e.target.value)}
              placeholder="z.B. itzg/minecraft-server"
              style={{ width: "100%", padding: 8, boxSizing: "border-box" }}
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            style={{ padding: "8px 20px", cursor: "pointer" }}
          >
            {submitting ? "Wird erstellt..." : "Blueprint erstellen"}
          </button>
        </form>
      </div>

      {/* Fehleranzeige */}
      {error && (
        <div
          style={{
            padding: 12,
            marginBottom: 16,
            backgroundColor: "#fee",
            border: "1px solid #c00",
            borderRadius: 4,
            color: "#c00",
          }}
        >
          {error}
        </div>
      )}

      {/* Blueprint-Liste */}
      {loading ? (
        <p>Blueprints werden geladen...</p>
      ) : blueprints.length === 0 ? (
        <p style={{ color: "#888" }}>Noch keine Blueprints vorhanden.</p>
      ) : (
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            border: "1px solid #ddd",
          }}
        >
          <thead>
            <tr style={{ backgroundColor: "#f5f5f5" }}>
              <th style={thStyle}>ID</th>
              <th style={thStyle}>Name</th>
              <th style={thStyle}>Beschreibung</th>
              <th style={thStyle}>Docker-Image</th>
              <th style={thStyle}>Erstellt</th>
            </tr>
          </thead>
          <tbody>
            {blueprints.map((bp) => (
              <tr key={bp.id}>
                <td style={tdStyle}>{bp.id}</td>
                <td style={tdStyle}>{bp.name}</td>
                <td style={tdStyle}>{bp.description || "–"}</td>
                <td style={tdStyle}>
                  {bp.docker_image ? (
                    <code>{bp.docker_image}</code>
                  ) : (
                    "–"
                  )}
                </td>
                <td style={tdStyle}>
                  {bp.created_at
                    ? new Date(bp.created_at).toLocaleString("de-CH")
                    : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: 10,
  textAlign: "left",
  borderBottom: "2px solid #ddd",
};

const tdStyle: React.CSSProperties = {
  padding: 10,
  borderBottom: "1px solid #eee",
};
