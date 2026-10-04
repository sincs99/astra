import { t } from "../../i18n";

interface AutoRefreshToggleProps {
  enabled: boolean;
  onChange: (value: boolean) => void;
  intervalSeconds: number;
}

export function AutoRefreshToggle({ enabled, onChange, intervalSeconds }: AutoRefreshToggleProps) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--fs-small)", color: "var(--text-2)", alignSelf: "flex-end", paddingBottom: 8 }}>
      <input type="checkbox" checked={enabled} onChange={(e) => onChange(e.target.checked)} />
      {t("common.autoRefresh", { seconds: intervalSeconds })}
    </label>
  );
}
