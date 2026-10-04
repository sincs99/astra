import { t } from "../../i18n";

/** Einheitlicher Leerzustand (M26). */

interface EmptyStateProps {
  message?: string;
  icon?: string;
}

export function EmptyState({ message = t("common.empty"), icon = "📭" }: EmptyStateProps) {
  return (
    <div style={{ padding: 32, textAlign: "center", color: "var(--fg-muted)" }}>
      <div style={{ fontSize: 32, marginBottom: 8 }}>{icon}</div>
      <div style={{ fontSize: 14 }}>{message}</div>
    </div>
  );
}
