import { useEffect, type ReactNode } from "react";
import { SiteFooter } from "./SiteFooter";

interface AuthCardProps {
  title: string;
  children: ReactNode;
}

/** Zentrierte Karte für öffentliche Seiten (Login, Registrierung, Passwort-Reset). */
export function AuthCard({ title, children }: AuthCardProps) {
  useEffect(() => { document.title = `${title} – Astra`; }, [title]);
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
    error: { bg: "var(--tint-red)", fg: "var(--c-red)" },
    success: { bg: "var(--tint-green)", fg: "var(--c-green)" },
    warning: { bg: "var(--tint-orange)", fg: "var(--c-orange)" },
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
