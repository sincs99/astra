import { fixUmlauts } from "./umlauts";
import { getLang, t } from "../i18n";

/** Allgemeine Meldungen, wenn das Backend nur einen technischen Statuscode liefert ("Request failed: 500"). */
function genericMessage(status: number): string {
  if (status >= 500) return t("error.server");
  if (status === 429) return t("error.tooMany");
  if (status === 404) return t("error.notFound");
  if (status === 403) return t("error.forbidden");
  return t("error.generic");
}

/**
 * Fehlermeldung für Nutzer: Der Server-Text gewinnt (er kommt in der Sprache der Oberfläche, M72); nur technische
 * Statuscodes ("Request failed: 500") werden durch die Frontend-Übersetzung ersetzt. Die ASCII-Umlaut-Korrekturen
 * (deutsche Altmeldungen) gelten nur in der deutschen Oberfläche.
 */
export function friendlyApiMessage(status: number, message: string): string {
  if (status === 403 && /^Admin-Berechtigung erforderlich/i.test(message)) {
    return t("error.adminOnly");
  }
  if (/^Request failed: \d+$/.test(message)) return genericMessage(status);
  return getLang() === "de" ? fixUmlauts(message) : message;
}

/** Meldung bei Netzwerkfehlern (Funktion, damit die aktuelle Sprache gilt). */
export const networkErrorMessage = (): string => t("error.network");
