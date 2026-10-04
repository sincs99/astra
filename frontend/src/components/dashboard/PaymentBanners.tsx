import { Link } from "react-router-dom";
import { t } from "../../i18n";
import type { Order } from "../../services/api";

const MAX_BANNERS = 2;

/** Hinweisbanner (role=status) für Bestellungen, die auf Zahlung warten; weitere werden zusammengefasst. */
export function PaymentBanners({ orders, onlinePayment, paying, onPay }: {
  orders: Order[];
  onlinePayment: boolean;
  paying: string | null;
  onPay: (order: Order) => void;
}) {
  if (orders.length === 0) return null;
  const shown = orders.slice(0, MAX_BANNERS);
  const rest = orders.length - shown.length;
  return (
    <>
      {shown.map((o) => (
        <div key={o.uuid} role="status" className="banner banner-warn">
          <span className="dot dot-warn" aria-hidden="true" />
          <span className="banner-text">
            {t(onlinePayment ? "dash.bannerOnline" : "dash.bannerManual", { name: o.instance_name })}
          </span>
          {onlinePayment ? (
            <button type="button" className="btn btn-sm btn-primary" disabled={paying === o.uuid} onClick={() => onPay(o)}>{t("dash.payCard")}</button>
          ) : (
            <Link to="/orders" className="btn btn-sm">{t("dash.showPayment")}</Link>
          )}
        </div>
      ))}
      {rest > 0 && (
        <div role="status" className="banner banner-warn">
          <span className="dot dot-warn" aria-hidden="true" />
          <span className="banner-text">{t("dash.moreBanners", { n: rest })}</span>
          <Link to="/orders" className="btn btn-sm">{t("dash.showPayment")}</Link>
        </div>
      )}
    </>
  );
}
