import { useState } from "react";
import { t } from "../../i18n";

/** "Zum Inhalt springen": nur bei Tastaturfokus sichtbar (WCAG 2.4.1). */
export function SkipLink() {
  const [focused, setFocused] = useState(false);
  return (
    <a
      href="#main-content"
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onClick={(e) => {
        e.preventDefault();
        const main = document.getElementById("main-content");
        main?.focus();
        main?.scrollIntoView?.();
      }}
      style={focused
        ? { position: "fixed", top: 8, left: 8, zIndex: 1000, padding: "8px 12px", background: "var(--bg-card)", color: "var(--c-blue)", border: "2px solid var(--c-blue)", borderRadius: 4, fontSize: 14 }
        : { position: "absolute", left: -9999, top: 0 }}
    >
      {t("common.skipToContent")}
    </a>
  );
}
