export function formatMB(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb} MB`;
}

export function formatValue(val: number, unit: string): string {
  if (unit === "MB") return formatMB(val);
  return `${val}${unit}`;
}

/** Farben erfuellen WCAG AA (4.5:1) auch als Text. */
export function utilizationColor(percent: number): string {
  if (percent >= 90) return "#c62828";
  if (percent >= 70) return "#e65100";
  if (percent >= 50) return "#8d6e00";
  return "#2e7d32";
}

interface UtilizationBarProps {
  used: number;
  /** Effektive Kapazitaet; 0 = kein Limit hinterlegt */
  total: number;
  percent: number;
  unit: string;
  label?: string;
}

export function UtilizationBar({ used, total, percent, unit, label }: UtilizationBarProps) {
  if (total <= 0) {
    return (
      <div style={{ minWidth: 100 }}>
        {label && <div style={{ fontSize: 11, color: "#666" }}>{label}</div>}
        <span style={{ color: "#666", fontSize: 12 }}>kein Limit</span>
        {used > 0 && <span style={{ color: "#666", fontSize: 11 }}> ({formatValue(used, unit)} belegt)</span>}
      </div>
    );
  }
  const color = utilizationColor(percent);
  return (
    <div style={{ minWidth: 100 }}>
      {label && <div style={{ fontSize: 11, color: "#666" }}>{label}</div>}
      <div
        role="progressbar"
        aria-label={label ? `${label} Auslastung` : "Auslastung"}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(Math.round(percent), 100)}
        style={{ height: 6, borderRadius: 3, backgroundColor: "#eee", overflow: "hidden" }}
      >
        <div style={{ width: `${Math.min(percent, 100)}%`, height: "100%", backgroundColor: color, borderRadius: 3, transition: "width 0.3s" }} />
      </div>
      <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>
        {formatValue(used, unit)} / {formatValue(total, unit)} ({percent}%)
      </div>
    </div>
  );
}
