import type { ReactNode } from "react";
import { SiteFooter } from "./SiteFooter";

interface AuthCardProps {
  title: string;
  children: ReactNode;
}

/** Zentrierte Karte fuer oeffentliche Seiten (Login, Registrierung, Passwort-Reset). */
export function AuthCard({ title, children }: AuthCardProps) {
  return (
    <div style={{ maxWidth: 400, margin: "clamp(24px, 10vh, 80px) auto", padding: 24 }}>
      <h1 style={{ textAlign: "center", marginBottom: 24 }}>{title}</h1>
      {children}
      <SiteFooter />
    </div>
  );
}

export function AuthMessage({ kind, children }: { kind: "error" | "success" | "warning"; children: ReactNode }) {
  const colors = {
    error: { bg: "#fce4e4", fg: "#c0392b" },
    success: { bg: "#e8f5e9", fg: "#2e7d32" },
    warning: { bg: "#fff3e0", fg: "#e65100" },
  }[kind];
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      style={{ padding: "10px 14px", backgroundColor: colors.bg, color: colors.fg, borderRadius: 6, marginBottom: 16, fontSize: 14 }}
    >
      {children}
    </div>
  );
}
