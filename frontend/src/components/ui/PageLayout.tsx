/**
 * App-Shell nach design/DESIGN.md: Seitenleiste links (einklappbar), mobil Kopfzeile mit Vollbild-Menü,
 * ausgeloggt eine schlanke Kopfzeile. Seitentitel mit optionalem Untertitel und Aktionen rechts.
 */

import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, isAuthenticated, logout } from "../../services/api";
import { SiteFooter } from "../SiteFooter";
import { SkipLink } from "./SkipLink";
import { FlashBanner } from "../FlashBanner";
import { Logo } from "./Logo";
import { Icon } from "./Icon";
import { loginUrl } from "../../lib/redirect";
import { useCurrentUser, resetCurrentUserCache } from "../../hooks/useCurrentUser";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { t } from "../../i18n";
import { NAV_ITEMS, activeHref, initials, type NavItem } from "../shell/navItems";
import { UserActions, UserMenu } from "../shell/UserMenu";
import type { User } from "../../services/api";

interface PageLayoutProps {
  title: string;
  /** Einzeiliger Untertitel unter dem Titel */
  subtitle?: React.ReactNode;
  /** Primäre Aktionen rechts neben dem Titel */
  actions?: React.ReactNode;
  /** Link "← Zurück" über dem Titel (z.B. von der Server-Detailseite zu "Meine Server") */
  back?: { to: string; label: string };
  children: React.ReactNode;
  maxWidth?: number;
}

const COLLAPSE_KEY = "astra_sidebar_collapsed";

function readCollapsed(): boolean {
  try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
}

function itemLabel(item: NavItem): string {
  return item.labelKey ? t(item.labelKey) : item.label;
}

function NavList({ items, current, collapsed, onNavigate }: { items: NavItem[]; current: string | null; collapsed: boolean; onNavigate?: () => void }) {
  let lastGroup: string | undefined;
  return (
    <>
      {items.map((item) => {
        const heading = item.group && item.group !== lastGroup ? item.group : null;
        lastGroup = item.group;
        return (
          <div key={item.href} style={{ display: "contents" }}>
            {heading && <div className="sb-label" aria-hidden="true">{heading}</div>}
            <Link to={item.href} className="sb-link" aria-current={current === item.href ? "page" : undefined}
              aria-label={collapsed ? itemLabel(item) : undefined} title={collapsed ? itemLabel(item) : undefined} onClick={onNavigate}>
              <Icon name={item.icon} />
              <span className="sb-text">{itemLabel(item)}</span>
            </Link>
          </div>
        );
      })}
    </>
  );
}

function PageHead({ title, subtitle, actions, back }: Pick<PageLayoutProps, "title" | "subtitle" | "actions" | "back">) {
  return (
    <>
    {back && <Link to={back.to} className="back-link"><Icon name="back" size={14} />{back.label}</Link>}
    <div className="page-head">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <div className="page-sub">{subtitle}</div>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
    </>
  );
}

export function PageLayout({ title, subtitle, actions, back, children, maxWidth = 1200 }: PageLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const isMobile = useMediaQuery("(max-width: 760px)");
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const user = useCurrentUser();

  // Browser-Tab-Titel folgt der Seite
  useEffect(() => { document.title = `${title} – Astra`; }, [title]);

  // Overlay schliessen bei Seitenwechsel, Escape oder Wechsel zur Desktop-Ansicht
  useEffect(() => { setMenuOpen(false); }, [location.pathname, isMobile]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0"); } catch { /* nur für diese Sitzung */ }
  };

  const handleLogout = async () => {
    // Token zuerst am Server sperren (best effort), danach immer lokal abmelden
    await api.logoutServer();
    logout();
    resetCurrentUserCache();
    navigate("/login");
  };

  const content = (
    <main id="main-content" tabIndex={-1} className="shell-content" style={{ maxWidth }}>
      <FlashBanner />
      <PageHead title={title} subtitle={subtitle} actions={actions} back={back} />
      {children}
    </main>
  );

  // Ausgeloggt (z.B. öffentlicher Shop): schlanke Kopfzeile ohne Konto-Navigation
  if (!isAuthenticated()) {
    const here = location.pathname + location.search;
    return (
      <div className="m-shell">
        <SkipLink />
        <header className="m-head">
          <Link to="/shop" className="sb-brand" aria-label={t("nav.home")}><Logo /></Link>
          <nav aria-label={t("nav.main")} style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <Link to={loginUrl(here)}>{t("nav.login")}</Link>
            <Link to={`/register?redirect=${encodeURIComponent(here)}`} className="menu-item"
              style={{ width: "auto", background: "var(--surface-2)", border: "1px solid var(--border)", color: "var(--text)" }}>{t("nav.register")}</Link>
          </nav>
        </header>
        <div className="shell-main">{content}<SiteFooter /></div>
      </div>
    );
  }

  const visible = NAV_ITEMS.filter((i) => !i.adminOnly || user?.is_admin);
  const current = activeHref(visible, location.pathname);

  if (isMobile) {
    return (
      <div className="m-shell">
        <SkipLink />
        <header className="m-head">
          <Link to="/" className="sb-brand" aria-label={t("nav.home")}><Logo /></Link>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span className="avatar" style={{ width: 32, height: 32 }} aria-hidden="true">{initials(user?.username)}</span>
            <button type="button" className="m-btn" aria-label={menuOpen ? t("nav.menuClose") : t("nav.menuOpen")}
              aria-expanded={menuOpen} aria-controls="mobile-menu" onClick={() => setMenuOpen(!menuOpen)}>
              <Icon name={menuOpen ? "close" : "menu"} size={20} />
            </button>
          </div>
        </header>
        {menuOpen && (
          <div id="mobile-menu" className="m-overlay" role="dialog" aria-modal="true" aria-label={t("nav.menu")}>
            <div className="m-head">
              <Link to="/" className="sb-brand" aria-label={t("nav.home")}><Logo /></Link>
              <button type="button" className="m-btn" aria-label={t("nav.menuClose")} onClick={() => setMenuOpen(false)}><Icon name="close" size={20} /></button>
            </div>
            <nav className="m-overlay-body" aria-label={t("nav.main")}>
              <NavList items={visible} current={current} collapsed={false} onNavigate={() => setMenuOpen(false)} />
              <div className="sb-sep" />
              <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: "0 4px" }}>
                <UserActions onLogout={handleLogout} onNavigate={() => setMenuOpen(false)} />
              </div>
            </nav>
          </div>
        )}
        <div className="shell-main">{content}<SiteFooter showLanguage={false} /></div>
      </div>
    );
  }

  return (
    <div className="shell">
      <SkipLink />
      <nav className={`sb${collapsed ? " sb-collapsed" : ""}`} aria-label={t("nav.main")}>
        <div className="sb-head">
          <Link to="/" className="sb-brand" aria-label={t("nav.home")}><Logo size={collapsed ? 22 : 24} wordmark={!collapsed} /></Link>
          <button type="button" className="icon-btn" aria-label={collapsed ? t("nav.expand") : t("nav.collapse")}
            aria-expanded={!collapsed} onClick={toggleCollapsed}><Icon name="panel" /></button>
        </div>
        <div className="sb-scroll"><NavList items={visible} current={current} collapsed={collapsed} /></div>
        <div className="sb-sep" />
        <UserMenu user={user as User | null} onLogout={handleLogout} />
      </nav>
      <div className="shell-main">{content}<SiteFooter showLanguage={false} /></div>
    </div>
  );
}
