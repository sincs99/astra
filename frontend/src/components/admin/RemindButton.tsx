import { useState } from "react";
import { api, ApiError, type Order } from "../../services/api";
import { t } from "../../i18n";

/** Status, bei denen eine Erinnerung sinnvoll ist (M69). */
export const REMINDABLE_STATUSES = ["active", "past_due", "pending_payment"];

type Result = { kind: "sent" } | { kind: "cooldown"; hours: number } | { kind: "error"; message: string };

/** "Erinnerung senden" je Bestellung: Rückmeldung inline (role=status), nach 409 ausgeblendet. */
export function RemindButton({ order }: { order: Pick<Order, "uuid" | "id" | "status"> }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  if (!REMINDABLE_STATUSES.includes(order.status) || unavailable) return null;

  const send = async () => {
    setBusy(true);
    setResult(null);
    try {
      await api.remindOrder(order.uuid);
      setResult({ kind: "sent" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        const seconds = Number(err.data?.retry_after_seconds);
        setResult({ kind: "cooldown", hours: Math.max(1, Math.ceil((Number.isFinite(seconds) ? seconds : 3600) / 3600)) });
      } else if (err instanceof ApiError && err.status === 409) {
        setUnavailable(true);
      } else {
        setResult({ kind: "error", message: err instanceof Error && err.message ? err.message : t("aorders.remindFailed") });
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <span style={{ display: "inline-flex", flexDirection: "column", gap: 4, alignItems: "flex-start" }}>
      <button type="button" className="btn btn-sm" disabled={busy} onClick={send}
        aria-label={t("aorders.remindAria", { id: order.id })}>
        {t("aorders.remind")}
      </button>
      {result && (
        <span role={result.kind === "error" ? "alert" : "status"} className={`hint${result.kind === "error" ? " text-danger" : ""}`}>
          {result.kind === "sent" ? t("aorders.reminded")
            : result.kind === "cooldown" ? t("aorders.remindCooldown", { n: result.hours })
            : result.message}
        </span>
      )}
    </span>
  );
}
