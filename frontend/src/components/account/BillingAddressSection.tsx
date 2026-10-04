import { useState } from "react";
import { t } from "../../i18n";
import { api, type User } from "../../services/api";
import { cardStyle, inputStyle, labelStyle, btnPrimary, ErrorState } from "../ui";

/** Konto: Rechnungsadresse (optional), erscheint auf den Rechnungen (M70). */
export function BillingAddressSection({ user, onSaved }: { user: Pick<User, "billing_name" | "billing_address">; onSaved: (message: string) => void }) {
  const [name, setName] = useState(user.billing_name ?? "");
  const [address, setAddress] = useState(user.billing_address ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setBusy(true);
      setError(null);
      await api.updateBillingAddress(name, address);
      onSaved(t("account.billing.saved"));
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : t("account.billing.failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section style={cardStyle} aria-labelledby="billing-title">
      <h2 id="billing-title" style={{ marginTop: 0, fontSize: 18 }}>{t("account.billing.title")}</h2>
      {error && <ErrorState message={error} />}
      <form onSubmit={submit} style={{ maxWidth: 420 }}>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="billing-name" style={labelStyle}>{t("account.billing.name")}</label>
          <input id="billing-name" type="text" autoComplete="name" maxLength={200} value={name}
            onChange={(e) => setName(e.target.value)} style={inputStyle} />
        </div>
        <div style={{ marginBottom: 8 }}>
          <label htmlFor="billing-address" style={labelStyle}>{t("account.billing.address")}</label>
          <textarea id="billing-address" rows={4} maxLength={500} autoComplete="street-address" value={address}
            aria-describedby="billing-hint" onChange={(e) => setAddress(e.target.value)} style={{ ...inputStyle, resize: "vertical" }} />
        </div>
        <p id="billing-hint" style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-3)" }}>{t("account.billing.hint")}</p>
        <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.7 : 1 }}>
          {busy ? t("account.billing.saving") : t("account.billing.save")}
        </button>
      </form>
    </section>
  );
}
