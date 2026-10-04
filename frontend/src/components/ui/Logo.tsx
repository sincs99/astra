/** Astra-Logo: Vier-Strahl-Stern (--accent) mit Satellitenpunkt (--text), optional mit Wortmarke (design/mockups/Logo.html). */
export function LogoMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true" focusable="false">
      <path d="M16 3 L18.6 13.4 L29 16 L18.6 18.6 L16 29 L13.4 18.6 L3 16 L13.4 13.4 Z" fill="var(--accent)" />
      {/* Unter 24 px entfällt der Satellit */}
      {size >= 24 && <circle cx="26" cy="6" r="2.4" fill="var(--text)" />}
    </svg>
  );
}

export function Logo({ size = 22, wordmark = true }: { size?: number; wordmark?: boolean }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 9, color: "var(--text)" }}>
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true" focusable="false">
        <path d="M16 3 L18.6 13.4 L29 16 L18.6 18.6 L16 29 L13.4 18.6 L3 16 L13.4 13.4 Z" fill="var(--accent)" />
        <circle cx="26" cy="6" r="2.4" fill="var(--text)" />
      </svg>
      {wordmark && <span style={{ fontSize: Math.round(size * 1.0), fontWeight: 600, letterSpacing: "-0.03em", lineHeight: 1 }}>Astra</span>}
    </span>
  );
}
