import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { takeFlash, type Flash } from "../lib/flash";
import { linkStyle } from "./ui/styles";
import { t } from "../i18n";

/** Zeigt einen einmaligen Hinweis (z.B. "Recovery-Code verwendet") über dem Seiteninhalt. */
export function FlashBanner() {
  const [flash, setFlash] = useState<Flash | null>(null);
  // takeFlash löscht den Eintrag; der Ref schützt vor dem doppelten Effekt-Lauf im StrictMode
  const taken = useRef(false);
  useEffect(() => {
    if (taken.current) return;
    taken.current = true;
    setFlash(takeFlash());
  }, []);
  if (!flash) return null;
  const warn = flash.kind === "warning";
  return (
    <div role={warn ? "alert" : "status"} style={{
      display: "flex", gap: 12, alignItems: "flex-start", justifyContent: "space-between",
      padding: "10px 14px", marginBottom: 16, borderRadius: 8, fontSize: 14,
      backgroundColor: warn ? "var(--warn-soft)" : "var(--accent-soft)",
      color: warn ? "var(--warn)" : "var(--accent)",
      border: `1px solid ${warn ? "var(--warn-border)" : "color-mix(in srgb, var(--accent) 35%, transparent)"}`,
    }}>
      <span>
        {flash.text}
        {flash.link && <> <Link to={flash.link.to} style={{ ...linkStyle, color: "inherit", textDecoration: "underline" }}>{flash.link.label}</Link></>}
      </span>
      <button type="button" onClick={() => setFlash(null)} aria-label={t("common.close")}
        style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", fontSize: 16, lineHeight: 1 }}>×</button>
    </div>
  );
}
