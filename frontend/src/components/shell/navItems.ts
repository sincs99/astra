import type { IconName } from "../ui/Icon";
import type { MessageKey } from "../../i18n";

export interface NavItem {
  /** Fester Text (Admin-Punkte bleiben unübersetzt) */
  label: string;
  /** Übersetzungsschlüssel für Kundenpunkte */
  labelKey?: MessageKey;
  href: string;
  icon: IconName;
  /** Überschrift der Gruppe in der Seitenleiste (nur Admin-Gruppen haben eine) */
  group?: string;
  adminOnly?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Meine Server", labelKey: "nav.dashboard", href: "/", icon: "servers" },
  { label: "Shop", labelKey: "nav.shop", href: "/shop", icon: "shop" },
  { label: "Meine Bestellungen", labelKey: "nav.orders", href: "/orders", icon: "orders" },
  { label: "Konto", labelKey: "nav.account", href: "/account", icon: "account" },
  { label: "SSH Keys", labelKey: "nav.sshKeys", href: "/account/ssh-keys", icon: "key" },

  { label: "Übersicht", href: "/admin", icon: "overview", group: "Core", adminOnly: true },
  { label: "Agents", href: "/admin/agents", icon: "servers", group: "Core", adminOnly: true },
  { label: "Blueprints", href: "/admin/blueprints", icon: "package", group: "Core", adminOnly: true },
  { label: "Instances", href: "/admin/instances", icon: "layers", group: "Core", adminOnly: true },
  { label: "Fleet Monitoring", href: "/admin/agents/monitoring", icon: "activity", group: "Operations", adminOnly: true },
  { label: "Jobs", href: "/admin/jobs", icon: "clock", group: "Operations", adminOnly: true },
  { label: "System", href: "/admin/system", icon: "settings", group: "Operations", adminOnly: true },
  { label: "Produkte", href: "/admin/products", icon: "tag", group: "Verkauf", adminOnly: true },
  { label: "Bestellungen", href: "/admin/orders", icon: "clipboard", group: "Verkauf", adminOnly: true },
  { label: "Rechnungen", href: "/admin/invoices", icon: "orders", group: "Verkauf", adminOnly: true },
  { label: "Webhooks", href: "/admin/webhooks", icon: "zap", group: "Integrations", adminOnly: true },
];

/** Aktiv ist der Eintrag mit dem längsten passenden Pfadpräfix (z.B. /admin/agents/monitoring statt /admin/agents). */
export function activeHref(items: NavItem[], pathname: string): string | null {
  let best: string | null = null;
  for (const i of items) {
    const match = i.href === "/" ? pathname === "/" : pathname === i.href || pathname.startsWith(i.href + "/");
    if (match && (!best || i.href.length > best.length)) best = i.href;
  }
  return best;
}

/** Initialen für den Avatar: "pascal.kone" -> "PK", "admin" -> "AD". */
export function initials(name: string | undefined): string {
  if (!name) return "…";
  const parts = name.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}
