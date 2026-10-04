/**
 * Einheitliches Seitenlayout mit Navigation (M26).
 *
 * Stellt eine konsistente Navigationsleiste und Seitenstruktur bereit.
 */

import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { linkStyle, btnDefault } from "./styles";
import { api, isAuthenticated, logout } from "../../services/api";
import { SkipLink } from "./SkipLink";
import { t, type MessageKey } from "../../i18n";
import { SiteFooter } from "../SiteFooter";
import { loginUrl } from "../../lib/redirect";
import { useCurrentUser, resetCurrentUserCache } from "../../hooks/useCurrentUser";
import { useMediaQuery } from "../../hooks/useMediaQuery";

interface NavItem {
  label: string;
  /** Übersetzungsschlüssel für Kundenpunkte; Admin-Punkte bleiben unübersetzt */
  labelKey?: MessageKey;
  href: string;
  group: string;
  /** Nur für Administratoren sichtbar */
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  // Core
  { label: "Dashboard", labelKey: "nav.dashboard", href: "/", group: "Core" },
  { label: "Übersicht", adminOnly: true, href: "/admin", group: "Core" },
  { label: "Agents", adminOnly: true, href: "/admin/agents", group: "Core" },
  { label: "Blueprints", adminOnly: true, href: "/admin/blueprints", group: "Core" },
  { label: "Instances", adminOnly: true, href: "/admin/instances", group: "Core" },
  // Operations
  { label: "Fleet Monitoring", adminOnly: true, href: "/admin/agents/monitoring", group: "Operations" },
  { label: "Jobs", adminOnly: true, href: "/admin/jobs", group: "Operations" },
  { label: "System", adminOnly: true, href: "/admin/system", group: "Operations" },
  // Shop (Phase 4)
  { label: "Shop", labelKey: "nav.shop", href: "/shop", group: "Shop" },
  { label: "Meine Bestellungen", labelKey: "nav.orders", href: "/orders", group: "Shop" },
  { label: "Produkte", href: "/admin/products", group: "Verkauf", adminOnly: true },
  { label: "Bestellungen", href: "/admin/orders", group: "Verkauf", adminOnly: true },
  // Integrations
  { label: "Webhooks", adminOnly: true, href: "/admin/webhooks", group: "Integrations" },
  // Account
  { label: "Konto", labelKey: "nav.account", href: "/account", group: "Account" },
  { label: "SSH Keys", labelKey: "nav.sshKeys", href: "/account/ssh-keys", group: "Account" },
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

  // Browser-Tab-Titel folgt der Seite
  useEffect(() => { document.title = `${title} – Astra`; }, [title]);

  // Menü schliessen bei Seitenwechsel, Escape oder Wechsel zur Desktop-Ansicht
  useEffect(() => { setMenuOpen(false); }, [currentPath, isMobile]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const user = useCurrentUser();
  // Während der User lädt, gelten die Admin-Links als nicht sichtbar (kein Flackern für Kunden)
  const navItems = NAV_ITEMS.filter((i) => (!i.adminOnly || user?.is_admin));
  const groups = Array.from(new Set(navItems.map((i) => i.group)));

  const handleLogout = async () => {
    // Token zuerst am Server sperren (best effort), danach immer lokal abmelden
    await api.logoutServer();
    logout();
    resetCurrentUserCache();
    navigate("/login");
  };

  // Ausgeloggt (z.B. öffentlicher Shop): schlanke Leiste ohne Konto-Navigation
  if (!isAuthenticated()) {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "var(--bg-page)" }}>
        <SkipLink />
        <nav aria-label={t("nav.main")} style={{
          backgroundColor: "var(--bg-card)", borderBottom: "1px solid var(--border)",
          padding: "0 clamp(12px, 4vw, 24px)", position: "sticky", top: 0, zIndex: 100,
        }}>
          <div style={{ maxWidth, margin: "0 auto", display: "flex", alignItems: "center", gap: 16, height: 48 }}>
            <Link to="/shop" style={{ ...linkStyle, fontWeight: 700, fontSize: 16 }}>Astra</Link>
            <div style={{ flex: 1 }} />
            <Link to={loginUrl(currentPath)} style={linkStyle}>{t("nav.login")}</Link>
            <Link to={`/register?redirect=${encodeURIComponent(currentPath)}`} style={{ ...btnDefault, textDecoration: "none", padding: "4px 12px", fontSize: 13 }}>
              {t("nav.register")}
            </Link>
          </div>
        </nav>
        <main id="main-content" tabIndex={-1} style={{ outline: "none", maxWidth, margin: "0 auto", padding: "16px clamp(12px, 4vw, 24px)", overflowX: "auto" }}>
          <h1 style={{ marginTop: 0, marginBottom: 20, fontSize: 24, fontWeight: 700 }}>{title}</h1>
          {children}
        </main>
        <SiteFooter />
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--bg-page)" }}>
      <SkipLink />
      {/* Navigation */}
      <nav aria-label="Hauptnavigation" style={{
        backgroundColor: "var(--bg-card)",
        borderBottom: "1px solid var(--border)",
        padding: "0 clamp(12px, 4vw, 24px)",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}>
        <div style={{
          maxWidth, margin: "0 auto",
          display: "flex", alignItems: "center", gap: 24,
          minHeight: 48, padding: "4px 0",
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
              aria-label={menuOpen ? t("nav.menuClose") : t("nav.menuOpen")}
              style={{ ...btnDefault, padding: "4px 12px", fontSize: 18, lineHeight: 1 }}
            >
              {menuOpen ? "✕" : "☰"}
            </button>
          )}
          {!isMobile && <div style={{ display: "flex", flexWrap: "wrap", gap: 2, fontSize: 13, flex: 1, minWidth: 0 }}>
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
                  backgroundColor: currentPath === item.href ? "var(--tint-blue)" : "transparent",
                  color: currentPath === item.href ? "var(--c-blue)" : "var(--fg-soft)",
                  whiteSpace: "nowrap",
                }}
              >
                {item.labelKey ? t(item.labelKey) : item.label}
              </Link>
            ))}
          </div>}
          {!isMobile && (
            <button
              type="button"
              onClick={handleLogout}
              style={{ ...btnDefault, padding: "4px 12px", fontSize: 13, flexShrink: 0 }}
            >
              {t("nav.logout")}
            </button>
          )}
        </div>

        {isMobile && menuOpen && (
          <div id="mobile-menu" style={{ paddingBottom: 12, maxHeight: "calc(100vh - 48px)", overflowY: "auto" }}>
            {groups.map((group) => (
              <div key={group} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: "var(--fg-muted)", padding: "4px 10px" }}>
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
                      backgroundColor: currentPath === item.href ? "var(--tint-blue)" : "transparent",
                      color: currentPath === item.href ? "var(--c-blue)" : "var(--fg)",
                    }}
                  >
                    {item.labelKey ? t(item.labelKey) : item.label}
                  </Link>
                ))}
              </div>
            ))}
            <button type="button" onClick={handleLogout} style={{ ...btnDefault, width: "100%", marginTop: 4 }}>
              {t("nav.logout")}
            </button>
          </div>
        )}
      </nav>

      {/* Content */}
      <main id="main-content" tabIndex={-1} style={{ outline: "none", maxWidth, margin: "0 auto", padding: "16px clamp(12px, 4vw, 24px)", overflowX: "auto" }}>
        <h1 style={{ marginTop: 0, marginBottom: 20, fontSize: 24, fontWeight: 700 }}>
          {title}
        </h1>
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
