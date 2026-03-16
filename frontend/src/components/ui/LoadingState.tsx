/** Einheitlicher Ladezustand (M26). */

interface LoadingStateProps {
  message?: string;
}

export function LoadingState({ message = "Wird geladen..." }: LoadingStateProps) {
  return (
    <div role="status" aria-busy="true" style={{ padding: 32, textAlign: "center", color: "#888" }}>
      <div style={{ fontSize: 24, marginBottom: 8 }}>&#8987;</div>
      <div style={{ fontSize: 14 }}>{message}</div>
    </div>
  );
}
