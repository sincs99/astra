/** Button mit Bestaetigungsdialog fuer gefaehrliche Aktionen (M26). */

import { useState } from "react";
import { btnDanger, btnDefault } from "./styles";

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
    const msg = confirmMessage || `"${label}" wirklich ausfuehren?`;
    if (!confirm(msg)) return;

    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  };

  const baseStyle = danger ? btnDanger : btnDefault;
  const padding = size === "sm" ? "4px 12px" : "8px 20px";
  const fontSize = size === "sm" ? 12 : 14;

  return (
    <button
      onClick={handleClick}
      disabled={disabled || busy}
      style={{
        ...baseStyle,
        padding,
        fontSize,
        opacity: disabled || busy ? 0.6 : 1,
        cursor: disabled || busy ? "not-allowed" : "pointer",
      }}
    >
      {busy ? "..." : label}
    </button>
  );
}
