import { t } from "../../i18n";

/** Einheitliche Fehleranzeige (M26). */

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" style={{
      padding: 16, marginBottom: 16, backgroundColor: "var(--tint-red)",
      border: "1px solid var(--border-red)", borderRadius: 8, color: "var(--c-red)",
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{t("common.error")}</div>
      <div style={{ fontSize: 14 }}>{message}</div>
      {onRetry && (
        <button type="button" onClick={onRetry} style={{
          marginTop: 8, padding: "6px 16px", borderRadius: 6,
          border: "1px solid var(--border-red)", backgroundColor: "var(--bg-card)", color: "var(--c-red)",
          cursor: "pointer", fontSize: 13, fontWeight: 600,
        }}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}
