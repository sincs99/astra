/**
 * Einheitliches Seitenlayout mit Navigation (M26).
 *
 * Stellt eine konsistente Navigationsleiste und Seitenstruktur bereit.
 */

import { Link, useLocation, useNavigate } from "react-router-dom";
import { linkStyle, btnDefault } from "./styles";
import { logout } from "../../services/api";

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
  // Account
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

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#fafafa" }}>
      {/* Navigation */}
      <nav aria-label="Hauptnavigation" style={{
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
          height: 48, overflowX: "auto",
        }}>
          <Link to="/" style={{ ...linkStyle, fontWeight: 700, fontSize: 16, marginRight: 8 }}>
            Astra
          </Link>
          <div style={{ display: "flex", gap: 4, fontSize: 13, flex: 1 }}>
            {NAV_ITEMS.map((item) => (
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
          </div>
          <button
            type="button"
            onClick={handleLogout}
            style={{ ...btnDefault, padding: "4px 12px", fontSize: 13, flexShrink: 0 }}
          >
            Abmelden
          </button>
        </div>
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
