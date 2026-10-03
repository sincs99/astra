/**
 * Feature-Flag fuer die Phase-4-Navigation (Shop, Bestellungen, Produkte).
 * Die Seiten sind immer ueber ihre URL erreichbar; Navigationseintraege und der Shop-Link
 * im Dashboard erscheinen erst mit VITE_SHOP_ENABLED=true (Build-Zeit), sobald das Backend bereit ist.
 */
export const SHOP_ENABLED = import.meta.env.VITE_SHOP_ENABLED === "true";
