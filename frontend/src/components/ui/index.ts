/**
 * Zentrale UI-Komponentenbibliothek (M26).
 *
 * Konventionen:
 * - Gruen (#4caf50): ready, running, healthy, completed, ok
 * - Blau (#1976d2): provisioning, starting, pending, info
 * - Gelb/Orange (#f57c00): stale, retrying, warning, maintenance
 * - Rot (#d32f2f): failed, error, degraded, stopped
 * - Grau (#888): offline, unknown, inactive, none
 */

export { StatusBadge } from "./StatusBadge";
export { LoadingState } from "./LoadingState";
export { ErrorState } from "./ErrorState";
export { EmptyState } from "./EmptyState";
export { ConfirmButton } from "./ConfirmButton";
export { Toast, useToast } from "./Toast";
export { PageLayout } from "./PageLayout";
export {
  cardStyle,
  inputStyle,
  labelStyle,
  btnPrimary,
  btnDanger,
  btnDefault,
  thStyle,
  tdStyle,
  linkStyle,
} from "./styles";
