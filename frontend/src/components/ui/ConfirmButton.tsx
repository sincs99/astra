/** Button mit Bestaetigungsdialog für gefährliche Aktionen (M26). */

import { useState } from "react";

interface ConfirmButtonProps {
  label: string;
  confirmMessage?: string;
  onConfirm: () => void | Promise<void>;
  danger?: boolean;
  disabled?: boolean;
  size?: "sm" | "md";
}

export function ConfirmButton({
  label,
  confirmMessage,
  onConfirm,
  danger = false,
  disabled = false,
  size = "md",
}: ConfirmButtonProps) {
  const [busy, setBusy] = useState(false);

  const handleClick = async () => {
    const msg = confirmMessage || `"${label}" wirklich ausführen?`;
    if (!confirm(msg)) return;

    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  };


  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || busy}
      className={`btn${size === "sm" ? " btn-sm" : ""}${danger ? " btn-danger-text" : ""}`}
    >
      {busy ? "..." : label}
    </button>
  );
}
