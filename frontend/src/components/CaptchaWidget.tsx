import { useEffect, useRef, useState } from "react";
import { getLang, t } from "../i18n";
import { CAPTCHA_SCRIPTS, loadScript, type CaptchaConfig } from "../lib/captcha";
import { captchaPrivacyNotice } from "../legal/captcha";

interface CaptchaApi {
  render: (el: HTMLElement, options: Record<string, unknown>) => string | number;
  reset: (id?: string | number) => void;
  remove?: (id?: string | number) => void;
}
declare global {
  interface Window { turnstile?: CaptchaApi; hcaptcha?: CaptchaApi }
}

interface CaptchaWidgetProps {
  config: CaptchaConfig;
  /** Token (oder null, wenn er abgelaufen ist oder die Prüfung fehlschlug) */
  onToken: (token: string | null) => void;
  /** Erhöhen, um das Widget zurückzusetzen (Tokens gelten nur einmal) */
  resetKey?: number;
}

/** Rendert Turnstile oder hCaptcha; ohne Anbieter wird nichts geladen und nichts angezeigt. */
export function CaptchaWidget({ config, onToken, resetKey = 0 }: CaptchaWidgetProps) {
  const host = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | number | null>(null);
  const callback = useRef(onToken);
  callback.current = onToken;
  const [loadFailed, setLoadFailed] = useState(false);
  const provider = config.provider;

  useEffect(() => {
    if (provider === "none" || !config.site_key) return;
    let cancelled = false;
    setLoadFailed(false);
    loadScript(CAPTCHA_SCRIPTS[provider])
      .then(() => {
        const api = provider === "turnstile" ? window.turnstile : window.hcaptcha;
        if (cancelled || !api || !host.current) return;
        const theme = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
        widgetId.current = api.render(host.current, {
          sitekey: config.site_key,
          theme,
          ...(provider === "turnstile" ? { language: getLang() } : { hl: getLang() }),
          callback: (token: string) => callback.current(token),
          "expired-callback": () => callback.current(null),
          "error-callback": () => callback.current(null),
        });
      })
      .catch(() => { if (!cancelled) setLoadFailed(true); });
    return () => {
      cancelled = true;
      const api = provider === "turnstile" ? window.turnstile : window.hcaptcha;
      if (widgetId.current !== null) api?.remove?.(widgetId.current);
      widgetId.current = null;
      callback.current(null);
    };
  }, [provider, config.site_key]);

  useEffect(() => {
    if (resetKey === 0 || widgetId.current === null) return;
    const api = provider === "turnstile" ? window.turnstile : window.hcaptcha;
    api?.reset(widgetId.current);
    callback.current(null);
  }, [resetKey, provider]);

  if (provider === "none") return null;
  return (
    <div style={{ marginBottom: 16 }}>
      <div ref={host} data-testid="captcha-host" />
      {loadFailed && <p role="alert" style={{ color: "var(--danger)", fontSize: 13, margin: "8px 0 0" }}>{t("auth.captcha.loadFailed")}</p>}
      <p style={{ color: "var(--text-3)", fontSize: 12, margin: "8px 0 0" }}>{captchaPrivacyNotice(provider)}</p>
    </div>
  );
}
