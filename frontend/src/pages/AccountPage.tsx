import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { t } from "../i18n";
import { api, type User } from "../services/api";
import { PageLayout, LoadingState, ErrorState, Toast, useToast, cardStyle, linkStyle } from "../components/ui";
import { PasswordSection } from "../components/account/PasswordSection";
import { MfaSection } from "../components/account/MfaSection";
import { ApiKeysSection } from "../components/account/ApiKeysSection";
import { ThemeSection } from "../components/account/ThemeSection";

/** Konto-Seite für alle eingeloggten Nutzer. */
export function AccountPage() {
  const toast = useToast();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    api.getCurrentUser().then(setUser).catch((err) =>
      setError(err instanceof Error ? err.message : t("account.loadFailed")));
  };

  useEffect(load, []);

  return (
    <PageLayout title={t("account.title")} maxWidth={800}>
      <Toast {...toast} />
      {error && <ErrorState message={error} onRetry={load} />}
      {!user && !error && <LoadingState />}
      {user && (
        <>
          <section style={cardStyle} aria-labelledby="profile-title">
            <h2 id="profile-title" style={{ marginTop: 0, fontSize: 18 }}>{t("account.profile")}</h2>
            <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "max-content 1fr", gap: "4px 16px" }}>
              <dt style={{ color: "var(--fg-soft)" }}>{t("account.username")}</dt><dd style={{ margin: 0 }}>{user.username}</dd>
              <dt style={{ color: "var(--fg-soft)" }}>{t("account.email")}</dt><dd style={{ margin: 0 }}>{user.email}</dd>
              <dt style={{ color: "var(--fg-soft)" }}>{t("account.role")}</dt><dd style={{ margin: 0 }}>{user.is_admin ? t("account.roleAdmin") : t("account.roleCustomer")}</dd>
            </dl>
            <p style={{ marginBottom: 0 }}>
              <Link to="/account/ssh-keys" style={linkStyle}>{t("account.manageKeys")}</Link>
            </p>
          </section>

          <ThemeSection />
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
