import { api, isAuthenticated, type User } from "../services/api";
import { isLang, setLang, type Lang } from "../i18n";

/**
 * Sprache wechseln: die Oberfläche sofort, und bei angemeldetem Nutzer zusätzlich die Sprache für Mails und Belege
 * am Konto speichern (M67). Fehler (auch ein Backend ohne das Feld) werden still ignoriert.
 */
export function changeLanguage(lang: Lang): void {
  setLang(lang);
  if (!isAuthenticated()) return;
  Promise.resolve()
    .then(() => api.updateAccountLocale(lang))
    .catch(() => {});
}

/** Nach dem Login: die am Konto gespeicherte Sprache übernehmen (null/fehlend = Auswahl dieses Browsers behalten). */
export function adoptUserLocale(user: Pick<User, "locale"> | null | undefined): void {
  if (user && isLang(user.locale)) setLang(user.locale);
}
