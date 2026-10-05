import { useEffect, type ReactNode } from "react";
import { SiteFooter } from "./SiteFooter";
import { OPERATOR } from "../legal/operator";

interface AuthCardProps {
  title: string;
  children: ReactNode;
}

/** Zentrierte Karte für öffentliche Seiten (Login, Registrierung, Passwort-Reset). */
export function AuthCard({ title, children }: AuthCardProps) {
  useEffect(() => { document.title = `${title} · ${OPERATOR.brand}`; }, [title]);
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
    error: { bg: "var(--danger-soft)", fg: "var(--danger)" },
    success: { bg: "color-mix(in srgb, var(--ok) 12%, transparent)", fg: "var(--ok)" },
    warning: { bg: "var(--warn-soft)", fg: "var(--warn)" },
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
