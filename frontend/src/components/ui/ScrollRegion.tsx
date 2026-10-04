import type { CSSProperties, ReactNode } from "react";

/** Horizontal scrollbarer Bereich (z.B. Tabelle); per Tastatur fokussierbar (WCAG 2.1.1). */
export function ScrollRegion({ label, children, style }: { label: string; children: ReactNode; style?: CSSProperties }) {
  return (
    <div role="region" aria-label={label} tabIndex={0} style={{ overflowX: "auto", ...style }}>
      {children}
    </div>
  );
}
