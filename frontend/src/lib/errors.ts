/** Übersetzt technische API-Fehler in verständliche Meldungen für Nutzer. */
export function friendlyApiMessage(status: number, message: string): string {
  if (status === 403 && /^Admin-Berechtigung erforderlich/i.test(message)) {
    return "Nur Administratoren dürfen diese Aktion ausführen.";
  }
  return message;
}

export const NETWORK_ERROR_MESSAGE = "Der Server ist nicht erreichbar. Bitte prüfe deine Verbindung und versuche es erneut.";
