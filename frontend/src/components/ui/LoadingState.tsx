import { t } from "../../i18n";

/** Einheitlicher Ladezustand (M26). */

interface LoadingStateProps {
  message?: string;
}

export function LoadingState({ message = t("common.loading") }: LoadingStateProps) {
  return <p role="status" aria-busy="true" className="hint" style={{ padding: 24, textAlign: "center" }}>{message}</p>;
}
