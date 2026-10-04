import { t } from "../../i18n";

/** Einheitlicher Leerzustand (M26). */

interface EmptyStateProps {
  message?: string;
  /** Veraltet: wird nicht mehr angezeigt */
  icon?: string;
}

export function EmptyState({ message = t("common.empty") }: EmptyStateProps) {
  return <p className="card-empty">{message}</p>;
}
