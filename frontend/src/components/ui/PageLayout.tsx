/**
 * Einheitliches Seitenlayout mit Navigation (M26).
 *
 * Stellt eine konsistente Navigationsleiste und Seitenstruktur bereit.
 */

import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { linkStyle, btnDefault } from "./styles";
import { logout } from "../../services/api";
import { useCurrentUser, resetCurrentUserCache } from "../../hooks/useCurrentUser";
import { useMediaQuery } from "../../hooks/useMediaQuery";

interface NavItem {
  label: string;
  href: string;
  group: string;
  /** Nur fuer Administratoren sichtbar */
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  // Core
  { label: "Dashboard", href: "/", group: "Core" },
  { label: "Agents", adminOnly: true, href: "/admin/agents", group: "Core" },
  { label: "Blueprints", adminOnly: true, href: "/admin/blueprints", group: "Core" },
  { label: "Instances", adminOnly: true, href: "/admin/instances", group: "Core" },
  // Operations
  { label: "Fleet Monitoring", adminOnly: true, href: "/admin/agents/monitoring", group: "Operations" },
  { label: "Jobs", adminOnly: true, href: "/admin/jobs", group: "Operations" },
  { label: "System", adminOnly: true, href: "/admin/system", group: "Operations" },
  // Shop (Phase 4)
  { label: "Shop", href: "/shop", group: "Shop" },
  { label: "Meine Bestellungen", href: "/orders", group: "Shop" },
  { label: "Produkte", href: "/admin/products", group: "Verkauf", adminOnly: true },
  { label: "Bestellungen", href: "/admin/orders", group: "Verkauf", adminOnly: true },
  // Integrations
  { label: "Webhooks", adminOnly: true, href: "/admin/webhooks", group: "Integrations" },
  // Account
  { label: "Konto", href: "/account", group: "Account" },
  { label: "SSH Keys", href: "/account/ssh-keys", group: "Account" },
];

interface PageLayoutProps {
  title: string;
  children: React.ReactNode;
  maxWidth?: number;
}

export function PageLayout({ title, children, maxWidth = 1100 }: PageLayoutProps) {
  const currentPath = useLocation().pathname;
  const navigate = useNavigate();
  const isMobile = useMediaQuery("(max-width: 760px)");
  const [menuOpen, setMenuOpen] = useState(false);

  // Menue schliessen bei Seitenwechsel, Escape oder Wechsel zur Desktop-Ansicht
  useEffect(() => { setMenuOpen(false); }, [currentPath, isMobile]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const user = useCurrentUser();
  // Waehrend der User laedt, gelten die Admin-Links als nicht sichtbar (kein Flackern fuer Kunden)
  const navItems = NAV_ITEMS.filter((i) => (!i.adminOnly || user?.is_admin));
  const groups = Array.from(new Set(navItems.map((i) => i.group)));

  const handleLogout = () => {
    logout();
    resetCurrentUserCache();
    navigate("/login");
  };

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#fafafa" }}>
      {/* Navigation */}
      <nav aria-label="Hauptnavigation" style={{
        backgroundColor: "#fff",
        borderBottom: "1px solid #e0e0e0",
        padding: "0 clamp(12px, 4vw, 24px)",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}>
        <div style={{
          maxWidth, margin: "0 auto",
          display: "flex", alignItems: "center", gap: 24,
          height: 48,
        }}>
          <Link to="/" style={{ ...linkStyle, fontWeight: 700, fontSize: 16, marginRight: 8, flexShrink: 0 }}>
            Astra
          </Link>
          {isMobile && <div style={{ flex: 1 }} />}
          {isMobile && (
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              aria-expanded={menuOpen}
              aria-controls="mobile-menu"
              aria-label={menuOpen ? "Menü schliessen" : "Menü öffnen"}
              style={{ ...btnDefault, padding: "4px 12px", fontSize: 18, lineHeight: 1 }}
            >
              {menuOpen ? "✕" : "☰"}
            </button>
          )}
          {!isMobile && <div style={{ display: "flex", gap: 4, fontSize: 13, flex: 1, minWidth: 0, overflowX: "auto" }}>
            {navItems.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                aria-current={currentPath === item.href ? "page" : undefined}
                style={{
                  ...linkStyle,
                  padding: "6px 10px",
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: currentPath === item.href ? 700 : 400,
                  backgroundColor: currentPath === item.href ? "#e3f2fd" : "transparent",
                  color: currentPath === item.href ? "#1565c0" : "#555",
                  whiteSpace: "nowrap",
                }}
              >
                {item.label}
              </Link>
            ))}
          </div>}
          {!isMobile && (
            <button
              type="button"
              onClick={handleLogout}
              style={{ ...btnDefault, padding: "4px 12px", fontSize: 13, flexShrink: 0 }}
            >
              Abmelden
            </button>
          )}
        </div>

        {isMobile && menuOpen && (
          <div id="mobile-menu" style={{ paddingBottom: 12, maxHeight: "calc(100vh - 48px)", overflowY: "auto" }}>
            {groups.map((group) => (
              <div key={group} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "#666", padding: "4px 10px" }}>
                  {group}
                </div>
                {navItems.filter((i) => i.group === group).map((item) => (
                  <Link
                    key={item.href}
                    to={item.href}
                    aria-current={currentPath === item.href ? "page" : undefined}
                    style={{
                      ...linkStyle,
                      display: "block",
                      padding: "10px",
                      borderRadius: 6,
                      fontSize: 15,
                      fontWeight: currentPath === item.href ? 700 : 400,
                      backgroundColor: currentPath === item.href ? "#e3f2fd" : "transparent",
                      color: currentPath === item.href ? "#1565c0" : "#333",
                    }}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            ))}
            <button type="button" onClick={handleLogout} style={{ ...btnDefault, width: "100%", marginTop: 4 }}>
              Abmelden
            </button>
          </div>
        )}
      </nav>

      {/* Content */}
      <main style={{ maxWidth, margin: "0 auto", padding: "16px clamp(12px, 4vw, 24px)", overflowX: "auto" }}>
        <h1 style={{ marginTop: 0, marginBottom: 20, fontSize: 24, fontWeight: 700 }}>
          {title}
        </h1>
        {children}
      </main>
    </div>
  );
}
