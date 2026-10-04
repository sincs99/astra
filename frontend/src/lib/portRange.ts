import { t } from "../i18n";
export interface PortRange {
  start: number;
  end: number;
}

/** Entspricht MAX_BULK_ENDPOINTS im Backend */
export const MAX_BULK_PORTS = 1000;

/**
 * Parst "25565" oder "25565-25600" (auch mit Leerzeichen / Gedankenstrich).
 * Liefert den Bereich oder eine Fehlermeldung als String.
 */
export function parsePortRange(input: string): PortRange | string {
  const text = input.trim().replace(/[\u2013\u2014]/g, "-");
  const m = /^(\d+)\s*(?:-\s*(\d+))?$/.exec(text);
  if (!m) return t("sform.portInput");
  const start = Number(m[1]);
  const end = m[2] === undefined ? start : Number(m[2]);
  if (start < 1 || start > 65535 || end < 1 || end > 65535) return t("sform.portRange");
  if (start > end) return t("sform.portOrder");
  const count = end - start + 1;
  if (count > MAX_BULK_PORTS) return t("sform.portMax", { max: MAX_BULK_PORTS, count });
  return { start, end };
}
