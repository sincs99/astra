import { useEffect, useState } from "react";
import QRCode from "qrcode";

/** Rendert den Text clientseitig als QR-Code (kein Secret verlässt den Browser). */
export function QrCode({ value, size = 180, alt }: { value: string; size?: number; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    QRCode.toDataURL(value, { width: size, margin: 1 })
      .then((url) => { if (!cancelled) setSrc(url); })
      .catch(() => { if (!cancelled) setSrc(null); });
    return () => { cancelled = true; };
  }, [value, size]);

  if (!src) return null;
  return <img src={src} width={size} height={size} alt={alt} style={{ border: "1px solid var(--border)", borderRadius: 6 }} />;
}
