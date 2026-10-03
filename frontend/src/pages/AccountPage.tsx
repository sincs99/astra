import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type User } from "../services/api";
import { PageLayout, LoadingState, ErrorState, Toast, useToast, cardStyle, linkStyle } from "../components/ui";
import { PasswordSection } from "../components/account/PasswordSection";
import { MfaSection } from "../components/account/MfaSection";
import { ApiKeysSection } from "../components/account/ApiKeysSection";

/** Konto-Seite fuer alle eingeloggten Nutzer. */
export function AccountPage() {
  const toast = useToast();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    api.getCurrentUser().then(setUser).catch((err) =>
      setError(err instanceof Error ? err.message : "Konto konnte nicht geladen werden"));
  };

  useEffect(load, []);

  return (
    <PageLayout title="Konto" maxWidth={800}>
      <Toast {...toast} />
      {error && <ErrorState message={error} onRetry={load} />}
      {!user && !error && <LoadingState />}
      {user && (
        <>
          <section style={cardStyle} aria-labelledby="profile-title">
            <h2 id="profile-title" style={{ marginTop: 0, fontSize: 18 }}>Profil</h2>
            <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "max-content 1fr", gap: "4px 16px" }}>
              <dt style={{ color: "#555" }}>Benutzername</dt><dd style={{ margin: 0 }}>{user.username}</dd>
              <dt style={{ color: "#555" }}>E-Mail</dt><dd style={{ margin: 0 }}>{user.email}</dd>
              <dt style={{ color: "#555" }}>Rolle</dt><dd style={{ margin: 0 }}>{user.is_admin ? "Administrator" : "Kunde"}</dd>
            </dl>
            <p style={{ marginBottom: 0 }}>
              <Link to="/account/ssh-keys" style={linkStyle}>SSH-Keys verwalten →</Link>
            </p>
          </section>

          <PasswordSection onChanged={toast.success} />
          <MfaSection
            enabled={!!user.mfa_enabled}
            onChanged={(enabled, message) => { setUser({ ...user, mfa_enabled: enabled }); toast.success(message); }}
          />
          <ApiKeysSection onMessage={toast.success} />
        </>
      )}
    </PageLayout>
  );
}
