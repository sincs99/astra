/**
 * Prueft ein `redirect`-Ziel aus der URL. Nur interne Pfade ("/shop") sind erlaubt,
 * damit der Login nicht als Open Redirect missbraucht werden kann ("//evil.com", "https://...").
 */
export function safeRedirectPath(value: string | null | undefined, fallback = "/"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return fallback;
  if (/[\u0000-\u001f]/.test(value)) return fallback;
  return value;
}

/** Login-Link, der nach der Anmeldung zurueck zur aktuellen Seite fuehrt. */
export function loginUrl(redirectTo: string): string {
  return `/login?redirect=${encodeURIComponent(redirectTo)}`;
}
