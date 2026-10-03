import { fixUmlauts } from "./umlauts";

/** Allgemeine Meldungen, wenn das Backend nur einen technischen Statuscode liefert ("Request failed: 500"). */
function genericMessage(status: number): string {
  if (status >= 500) return "Auf dem Server ist ein Fehler aufgetreten. Bitte versuche es später erneut.";
  if (status === 429) return "Zu viele Anfragen. Bitte warte einen Moment und versuche es dann erneut.";
  if (status === 404) return "Das wurde nicht gefunden.";
  if (status === 403) return "Dafür fehlt dir die Berechtigung.";
  return "Die Anfrage konnte nicht verarbeitet werden. Bitte prüfe deine Eingaben und versuche es erneut.";
}

/** Übersetzt technische API-Fehler in verständliche Meldungen für Nutzer. */
export function friendlyApiMessage(status: number, message: string): string {
  if (status === 403 && /^Admin-Berechtigung erforderlich/i.test(message)) {
    return "Nur Administratoren dürfen diese Aktion ausführen.";
  }
  if (/^Request failed: \d+$/.test(message)) return genericMessage(status);
  return fixUmlauts(message);
}

export const NETWORK_ERROR_MESSAGE = "Der Server ist nicht erreichbar. Bitte prüfe deine Verbindung und versuche es erneut.";
