import { Link } from "react-router-dom";
import { t } from "../i18n";
import { LanguageSwitch } from "./LanguageSwitch";

const links = () => [
  { to: "/impressum", label: t("footer.imprint") },
  { to: "/datenschutz", label: t("footer.privacy") },
  { to: "/agb", label: t("footer.terms") },
];

/** Fusszeile mit den Rechtslinks; auf allen Seiten (auch Login und Registrierung) eingebunden. */
export function SiteFooter({ showLanguage = true }: { showLanguage?: boolean }) {
  return (
    <footer style={{ textAlign: "center", padding: "24px 16px", fontSize: 13, color: "var(--fg-muted)" }}>
      <nav aria-label={t("footer.legalNav")} style={{ display: "inline-flex", gap: 16, flexWrap: "wrap", justifyContent: "center" }}>
        {links().map((l) => (
          <Link key={l.to} to={l.to} style={{ color: "var(--c-blue)", textDecoration: "underline" }}>{l.label}</Link>
        ))}
      </nav>
      {showLanguage && <div style={{ marginTop: 8 }}><LanguageSwitch /></div>}
    </footer>
  );
}
