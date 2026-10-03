interface AutoRefreshToggleProps {
  enabled: boolean;
  onChange: (value: boolean) => void;
  intervalSeconds: number;
}

export function AutoRefreshToggle({ enabled, onChange, intervalSeconds }: AutoRefreshToggleProps) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#555", alignSelf: "flex-end", paddingBottom: 8 }}>
      <input type="checkbox" checked={enabled} onChange={(e) => onChange(e.target.checked)} />
      Auto-Refresh ({intervalSeconds}s)
    </label>
  );
}
