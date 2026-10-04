import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Product } from "../services/api";
import { Logo } from "../components/ui/Logo";
import { Icon } from "../components/ui/Icon";
import { LanguageSwitch } from "../components/LanguageSwitch";
import { formatMoney, formatPeriod } from "../lib/money";
import { formatMemory } from "../lib/dashboard";
import { OPERATOR, isPlaceholder } from "../legal/operator";
import { dateLocale, t } from "../i18n";

/** Öffentliche Startseite (/ ohne Anmeldung) nach design/mockups/Landing.html; Pakete kommen aus GET /api/client/products. */
export function LandingPage() {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [onlinePayment, setOnlinePayment] = useState<boolean | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const [list, billing] = await Promise.all([api.getShopProducts(), api.getBillingInfo().catch(() => null)]);
      setProducts(list);
      if (billing) setOnlinePayment(billing.online_payment);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { document.title = t("landing.title"); }, []);

  // Spiele: nur was die Pakete tatsächlich nennen (Blueprint-Namen), keine erfundene Liste
  const games = Array.from(new Set((products ?? []).map((p) => p.blueprint_name).filter((g): g is string => !!g)));
  const locale = dateLocale();
  const trust = [
    t("landing.trustPanel"),
    ...(onlinePayment === null ? [] : [onlinePayment ? t("landing.trustCard") : t("landing.trustTransfer")]),
    t("landing.trustNoSub"),
  ];
  const stepTwo = onlinePayment ? t("landing.step2Card") : t("landing.step2Transfer");

  return (
    <div className="lp">
      <header className="lp-head">
        <div className="lp-wrap">
          <div className="lp-nav">
            <Link to="/" className="sb-brand" aria-label="Astra"><Logo size={24} /></Link>
            <nav aria-label={t("landing.navAria")} className="lp-links">
              <a href="#pakete">{t("landing.navPackages")}</a>
              {games.length > 0 && <a href="#spiele">{t("landing.navGames")}</a>}
              <a href="#ablauf">{t("landing.navSteps")}</a>
            </nav>
            <div className="lp-cta">
              <Link to="/login" className="btn btn-ghost" style={{ color: "var(--text)" }}>{t("landing.login")}</Link>
              <a href="#pakete" className="btn btn-primary">{t("landing.order")}</a>
              <button type="button" className="m-btn lp-burger" aria-label={t("landing.menu")} aria-expanded={menuOpen}
                aria-controls="lp-menu" onClick={() => setMenuOpen(!menuOpen)}>
                <Icon name={menuOpen ? "close" : "menu"} size={20} />
              </button>
            </div>
          </div>
          {menuOpen && (
            <nav id="lp-menu" className="lp-menu" aria-label={t("landing.navAria")}>
              <a href="#pakete" onClick={() => setMenuOpen(false)}>{t("landing.navPackages")}</a>
              {games.length > 0 && <a href="#spiele" onClick={() => setMenuOpen(false)}>{t("landing.navGames")}</a>}
              <a href="#ablauf" onClick={() => setMenuOpen(false)}>{t("landing.navSteps")}</a>
            </nav>
          )}
        </div>
      </header>

      <main id="main-content" tabIndex={-1} style={{ outline: "none" }}>
        <section className="lp-hero">
          <div className="lp-wrap">
            {games.length > 0 && <span className="mono lp-kicker">{games.join(" · ")}</span>}
            <h1 className="lp-h1">{t("landing.h1")}</h1>
            <p className="lp-lead">{t("landing.lead")}</p>
            <div className="lp-btns">
              <a href="#pakete" className="btn btn-primary">{t("landing.seePlans")}</a>
              <a href="#ablauf" className="btn">{t("landing.seeSteps")}</a>
            </div>
            <div className="lp-trust">{trust.map((x) => <span key={x}>{x}</span>)}</div>
          </div>
        </section>

        <section id="pakete" className="lp-section" aria-labelledby="lp-plans">
          <div className="lp-wrap">
            <div>
              <h2 id="lp-plans" className="lp-h2">{t("landing.plansTitle")}</h2>
              <p className="lp-sub">{t("landing.plansSub")}</p>
            </div>
            {failed ? (
              <div className="card-empty" role="alert">
                <p style={{ margin: "0 0 8px" }}>{t("landing.plansFailed")}</p>
                <button type="button" className="btn btn-sm" onClick={load}>{t("landing.retry")}</button>
              </div>
            ) : products === null ? (
              <p className="hint" role="status">{t("common.loading")}</p>
            ) : products.length === 0 ? (
              <div className="card-empty">{t("landing.plansNone")}</div>
            ) : (
              <div className="lp-cards">
                {products.map((p) => (
                  <article key={p.id} className="lp-card" aria-labelledby={`lp-p-${p.id}`}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <h3 id={`lp-p-${p.id}`} style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{p.name}</h3>
                      {p.description && <span className="card-sub">{p.description}</span>}
                    </div>
                    <div className="lp-price">
                      <span className="mono">{formatMoney(p.price_cents, p.currency)}</span>
                      <span>{t("landing.perPeriod", { period: formatPeriod(p.billing_period_days) })}</span>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      <div className="lp-check"><Icon name="check" size={16} /><span>{t("landing.spec1", { ram: formatMemory(p.resources.memory, locale), cpu: p.resources.cpu })}</span></div>
                      <div className="lp-check"><Icon name="check" size={16} /><span>{t("landing.spec2", { disk: formatMemory(p.resources.disk, locale) })}</span></div>
                      {p.blueprint_name && <div className="lp-check"><Icon name="check" size={16} /><span>{t("landing.specGame", { game: p.blueprint_name })}</span></div>}
                    </div>
                    <Link to={`/shop?plan=${p.id}`} className="btn" style={{ marginTop: "auto", height: 40 }}
                      aria-label={`${t("landing.order")}: ${p.name}`}>{t("landing.order")}</Link>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>

        {games.length > 0 && (
          <section id="spiele" className="lp-section" aria-labelledby="lp-games" style={{ paddingTop: 0 }}>
            <div className="lp-wrap">
              <div>
                <h2 id="lp-games" className="lp-h2">{t("landing.gamesTitle")}</h2>
                <p className="lp-sub">{t("landing.gamesSub")}</p>
              </div>
              <ul className="lp-games" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {games.map((g) => (
                  <li key={g} className="lp-game"><span className="lp-mono" aria-hidden="true">{g.slice(0, 2).toUpperCase()}</span>{g}</li>
                ))}
              </ul>
            </div>
          </section>
        )}

        <section id="ablauf" className="lp-section" aria-labelledby="lp-steps" style={{ paddingTop: 0, paddingBottom: 88 }}>
          <div className="lp-wrap">
            <h2 id="lp-steps" className="lp-h2">{t("landing.stepsTitle")}</h2>
            <ol className="lp-steps" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              <li className="lp-step"><span className="mono">01</span><strong>{t("landing.step1")}</strong><span>{t("landing.step1Text")}</span></li>
              <li className="lp-step"><span className="mono">02</span><strong>{t("landing.step2")}</strong><span>{stepTwo}</span></li>
              <li className="lp-step"><span className="mono">03</span><strong>{t("landing.step3")}</strong><span>{t("landing.step3Text")}</span></li>
            </ol>
          </div>
        </section>
      </main>

      <footer className="lp-foot">
        <div className="lp-wrap">
          <div className="lp-foot-row">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Logo size={18} wordmark={false} />
              <span>{t("landing.footerBrand")}{!isPlaceholder(OPERATOR.name) && ` · ${OPERATOR.name}`}</span>
            </div>
            <nav aria-label={t("landing.footerNav")}>
              <Link to="/impressum">{t("footer.imprint")}</Link>
              <Link to="/datenschutz">{t("footer.privacy")}</Link>
              <Link to="/agb">{t("footer.terms")}</Link>
            </nav>
            <LanguageSwitch />
          </div>
        </div>
      </footer>
    </div>
  );
}
