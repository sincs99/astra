export type CaptchaProvider = "none" | "turnstile" | "hcaptcha";

export interface CaptchaConfig {
  provider: CaptchaProvider;
  site_key: string | null;
}

export const NO_CAPTCHA: CaptchaConfig = { provider: "none", site_key: null };

/** Nur diese beiden Quellen werden je geladen (und nur, wenn der Server den Anbieter meldet). */
export const CAPTCHA_SCRIPTS: Record<Exclude<CaptchaProvider, "none">, string> = {
  turnstile: "https://challenges.cloudflare.com/turnstile/v0/api.js",
  hcaptcha: "https://js.hcaptcha.com/1/api.js",
};

/** Antwort von /auth/captcha prüfen: unbekannter Anbieter oder fehlender Site-Key gilt als "none". */
export function normalizeCaptchaConfig(raw: unknown): CaptchaConfig {
  const r = raw as Partial<CaptchaConfig> | null | undefined;
  if ((r?.provider === "turnstile" || r?.provider === "hcaptcha") && typeof r.site_key === "string" && r.site_key) {
    return { provider: r.provider, site_key: r.site_key };
  }
  return NO_CAPTCHA;
}

const loading = new Map<string, Promise<void>>();

/** Lädt ein Script genau einmal; löst auf, sobald es geladen ist. */
export function loadScript(src: string): Promise<void> {
  const existing = loading.get(src);
  if (existing) return existing;
  const promise = new Promise<void>((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src;
    el.async = true;
    el.defer = true;
    el.addEventListener("load", () => resolve());
    el.addEventListener("error", () => { loading.delete(src); el.remove(); reject(new Error("captcha script failed")); });
    document.head.appendChild(el);
  });
  loading.set(src, promise);
  return promise;
}

/** Nur für Tests: gemerkte Ladevorgänge verwerfen. */
export function resetCaptchaScriptsForTests(): void {
  loading.clear();
}
