import { cloneElement, isValidElement, useId } from "react";

/** Label mit Eingabefeld in der .field-Sprache; das erste Kind bekommt die id automatisch (Label-Verknüpfung). */
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  const id = useId();
  const kids = Array.isArray(children) ? children : [children];
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {kids.map((c, i) => (i === 0 && isValidElement(c) ? cloneElement(c as React.ReactElement<{ id?: string }>, { id }) : c))}
    </div>
  );
}

/** Responsives Formularraster: so viele Spalten wie mit mindestens `min` px Breite passen. */
export const fieldGrid = (min: number): React.CSSProperties => ({
  display: "grid", gridTemplateColumns: `repeat(auto-fit, minmax(min(${min}px, 100%), 1fr))`, gap: "var(--space-card)",
});

/** Fehlerbanner (role=alert) mit optionalem "Erneut versuchen". */
export function ErrorBanner({ message, title, retryLabel, onRetry }: { message: string; title?: string; retryLabel?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="banner banner-danger">
      <span className="dot dot-danger" aria-hidden="true" />
      <span className="banner-text">{title && <strong>{title} </strong>}{message}</span>
      {onRetry && <button type="button" className="btn btn-sm" onClick={onRetry}>{retryLabel}</button>}
    </div>
  );
}
