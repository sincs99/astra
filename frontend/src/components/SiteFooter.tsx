import { Link } from "react-router-dom";

const LINKS = [
  { to: "/impressum", label: "Impressum" },
  { to: "/datenschutz", label: "Datenschutz" },
  { to: "/agb", label: "AGB" },
];

/** Fusszeile mit den Rechtslinks; auf allen Seiten (auch Login und Registrierung) eingebunden. */
export function SiteFooter() {
  return (
    <footer style={{ textAlign: "center", padding: "24px 16px", fontSize: 13, color: "var(--fg-muted)" }}>
      <nav aria-label="Rechtliches" style={{ display: "inline-flex", gap: 16, flexWrap: "wrap", justifyContent: "center" }}>
        {LINKS.map((l) => (
          <Link key={l.to} to={l.to} style={{ color: "var(--c-blue)", textDecoration: "underline" }}>{l.label}</Link>
        ))}
      </nav>
    </footer>
  );
}
