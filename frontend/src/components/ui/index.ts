/**
 * Zentrale UI-Komponentenbibliothek (M26).
 *
 * Konventionen:
 * - Gruen (--ok): ready, running, healthy, completed, ok
 * - Blau/Akzent (--accent): provisioning, starting, pending, info
 * - Gelb/Orange (--warn): stale, retrying, warning, maintenance
 * - Rot (--danger): failed, error, degraded, stopped
 * - Grau (--neutral): offline, unknown, inactive, none
 */

export { StatusBadge, statusLabel } from "./StatusBadge";
export { LoadingState } from "./LoadingState";
export { ErrorState } from "./ErrorState";
export { EmptyState } from "./EmptyState";
export { ConfirmButton } from "./ConfirmButton";
export { Toast, useToast } from "./Toast";
export { PageLayout } from "./PageLayout";
export { ScrollRegion } from "./ScrollRegion";
export { AutoRefreshToggle } from "./AutoRefreshToggle";
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
