import { useState } from "react";

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
        ? { position: "fixed", top: 8, left: 8, zIndex: 1000, padding: "8px 12px", background: "#fff", color: "#1565c0", border: "2px solid #1565c0", borderRadius: 4, fontSize: 14 }
        : { position: "absolute", left: -9999, top: 0 }}
    >
      Zum Inhalt springen
    </a>
  );
}
