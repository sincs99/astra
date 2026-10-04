import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../ui/Icon";
import { LANG_OPTIONS, t, useLang } from "../../i18n";
import { changeLanguage } from "../../lib/locale";
import { getThemePreference, setThemePreference, themeOptions, type ThemePreference } from "../../lib/theme";
import { initials } from "./navItems";
import type { User } from "../../services/api";

/** Sprache, Design, Konto und Abmelden; wird im Popover der Seitenleiste und im Mobil-Overlay verwendet. */
export function UserActions({ onLogout, onNavigate }: { onLogout: () => void; onNavigate?: () => void }) {
  const lang = useLang();
  const [theme, setTheme] = useState<ThemePreference>(getThemePreference);

  return (
    <>
      <div className="menu-row">
        <span id="um-lang">{t("nav.language")}</span>
        <div className="seg" role="group" aria-labelledby="um-lang">
          {LANG_OPTIONS.map((o) => (
            <button key={o.value} type="button" lang={o.value} aria-pressed={lang === o.value} onClick={() => changeLanguage(o.value)}>{o.label}</button>
          ))}
        </div>
      </div>
      <div className="menu-row">
        <span id="um-theme">{t("nav.theme")}</span>
        <div className="seg" role="group" aria-labelledby="um-theme">
          {themeOptions().map((o) => (
            <button key={o.value} type="button" aria-pressed={theme === o.value}
              onClick={() => { setTheme(o.value); setThemePreference(o.value); }}>{o.label}</button>
          ))}
        </div>
      </div>
      <Link to="/account" className="menu-item" onClick={onNavigate}><Icon name="account" />{t("nav.account")}</Link>
      <button type="button" className="menu-item" onClick={onLogout}><Icon name="logout" />{t("nav.logout")}</button>
    </>
  );
}

/** Nutzerzeile unten in der Seitenleiste mit aufklappbarem Menü. */
export function UserMenu({ user, onLogout }: { user: User | null; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    const onClick = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onClick); };
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {open && (
        <div className="user-menu" role="group" aria-label={t("nav.userMenu")}>
          <UserActions onLogout={onLogout} onNavigate={() => setOpen(false)} />
        </div>
      )}
      <button type="button" className="user-btn" aria-expanded={open} aria-label={t("nav.userMenu")} onClick={() => setOpen(!open)}>
        <span className="avatar" aria-hidden="true">{initials(user?.username)}</span>
        <span className="sb-text" style={{ display: "flex", flexDirection: "column", minWidth: 0, flex: "1 1 auto" }}>
          <span style={{ fontSize: "var(--fs-small)", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.username ?? "…"}</span>
          <span style={{ fontSize: 11, color: "var(--text-3)" }}>{user ? (user.is_admin ? t("nav.adminRole") : t("nav.customerRole")) : ""}</span>
        </span>
        <span className="sb-text" style={{ color: "var(--text-3)", display: "inline-flex" }}><Icon name="chevrons" /></span>
      </button>
    </div>
  );
}
