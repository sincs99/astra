import { t } from "../../i18n";

/** Einheitliche Fehleranzeige (M26). */

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" className="banner banner-danger" style={{ marginBottom: 16 }}>
      <div className="banner-text">
        <strong style={{ display: "block" }}>{t("common.error")}</strong>
        <span>{message}</span>
      </div>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>{t("common.retry")}</button>
      )}
    </div>
  );
}
