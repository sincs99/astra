import { getLang } from "../i18n";
import type { CaptchaProvider } from "../lib/captcha";

/**
 * Datenschutzhinweis unter Formularen mit Captcha. Der Betreiber passt die Texte an (Anbieter, Zweck, Rechtsgrundlage);
 * er wird nur angezeigt, wenn ein externer Captcha-Dienst aktiv ist.
 */
const NAMES: Record<Exclude<CaptchaProvider, "none">, string> = { turnstile: "Cloudflare Turnstile", hcaptcha: "hCaptcha" };

export function captchaPrivacyNotice(provider: Exclude<CaptchaProvider, "none">): string {
  const name = NAMES[provider];
  return getLang() === "en"
    ? `This form is protected by ${name}. Your browser connects to the provider for this check; see our privacy policy.`
    : `Dieses Formular ist durch ${name} geschützt. Dafür verbindet sich dein Browser mit dem Anbieter; Details in der Datenschutzerklärung.`;
}
