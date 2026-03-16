/** Einheitlicher Leerzustand (M26). */

interface EmptyStateProps {
  message?: string;
  icon?: string;
}

export function EmptyState({ message = "Keine Daten vorhanden.", icon = "📭" }: EmptyStateProps) {
  return (
    <div style={{ padding: 32, textAlign: "center", color: "#999" }}>
      <div style={{ fontSize: 32, marginBottom: 8 }}>{icon}</div>
      <div style={{ fontSize: 14 }}>{message}</div>
    </div>
  );
}
