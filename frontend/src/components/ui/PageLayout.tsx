/**
 * Einheitliches Seitenlayout mit Navigation (M26).
 *
 * Stellt eine konsistente Navigationsleiste und Seitenstruktur bereit.
 */

import { linkStyle } from "./styles";

interface NavItem {
  label: string;
  href: string;
  group: string;
}

const NAV_ITEMS: NavItem[] = [
  // Core
  { label: "Dashboard", href: "/", group: "Core" },
  { label: "Agents", href: "/admin/agents", group: "Core" },
  { label: "Blueprints", href: "/admin/blueprints", group: "Core" },
  { label: "Instances", href: "/admin/instances", group: "Core" },
  // Operations
  { label: "Fleet Monitoring", href: "/admin/agents/monitoring", group: "Operations" },
  { label: "Jobs", href: "/admin/jobs", group: "Operations" },
  { label: "System", href: "/admin/system", group: "Operations" },
  // Integrations
  { label: "Webhooks", href: "/admin/webhooks", group: "Integrations" },
];

interface PageLayoutProps {
  title: string;
  children: React.ReactNode;
  maxWidth?: number;
}

export function PageLayout({ title, children, maxWidth = 1100 }: PageLayoutProps) {
  const currentPath = typeof window !== "undefined" ? window.location.pathname : "";

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#fafafa" }}>
      {/* Navigation */}
      <nav style={{
        backgroundColor: "#fff",
        borderBottom: "1px solid #e0e0e0",
        padding: "0 24px",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}>
        <div style={{
          maxWidth, margin: "0 auto",
          display: "flex", alignItems: "center", gap: 24,
          height: 48, overflow: "auto",
        }}>
          <a href="/" style={{ ...linkStyle, fontWeight: 700, fontSize: 16, marginRight: 8 }}>
            Astra
          </a>
          <div style={{ display: "flex", gap: 4, fontSize: 13 }}>
            {NAV_ITEMS.map((item) => (
              <a
                key={item.href}
                href={item.href}
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
              </a>
            ))}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main style={{ maxWidth, margin: "0 auto", padding: 24 }}>
        <h1 style={{ marginTop: 0, marginBottom: 20, fontSize: 24, fontWeight: 700 }}>
          {title}
        </h1>
        {children}
      </main>
    </div>
  );
}
