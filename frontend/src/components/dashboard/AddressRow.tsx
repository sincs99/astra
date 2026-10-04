import { useState } from "react";
import { Icon } from "../ui/Icon";
import { t } from "../../i18n";

/** Verbindungsadresse in der Konsolen-Zeile (Mono, --console) mit Kopieren-Button; ohne Adresse ein gedimmter Platzhalter. */
export function AddressRow({ address, placeholder }: { address?: string | null; placeholder?: string }) {
  const [copied, setCopied] = useState(false);

  if (!address) {
    return (
      <div className="addr addr-muted">
        <span className="mono">{placeholder ?? "–"}</span>
      </div>
    );
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(address);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Zwischenablage nicht verfügbar: Adresse bleibt sichtbar und markierbar
    }
  };

  return (
    <div className="addr">
      <span className="mono" title={address} style={{ userSelect: "all" }}>{address}</span>
      <button type="button" className="btn btn-sm" style={{ height: 28, padding: "0 9px", fontSize: 12 }} onClick={copy}
        aria-label={t("orders.copyAria", { address })}>
        <Icon name="copy" size={13} />{copied ? t("orders.copied") : t("orders.copy")}
      </button>
      <span role="status" style={{ position: "absolute", left: -9999 }}>{copied ? t("orders.copiedStatus") : ""}</span>
    </div>
  );
}
