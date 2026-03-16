/** Einheitliche Fehleranzeige (M26). */

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" style={{
      padding: 16, marginBottom: 16, backgroundColor: "#ffebee",
      border: "1px solid #ef9a9a", borderRadius: 8, color: "#c62828",
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Fehler</div>
      <div style={{ fontSize: 14 }}>{message}</div>
      {onRetry && (
        <button onClick={onRetry} style={{
          marginTop: 8, padding: "6px 16px", borderRadius: 6,
          border: "1px solid #ef9a9a", backgroundColor: "#fff", color: "#c62828",
          cursor: "pointer", fontSize: 13, fontWeight: 600,
        }}>
          Erneut versuchen
        </button>
      )}
    </div>
  );
}
