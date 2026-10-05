// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Logo } from "../components/ui/Logo";
import { PageLayout } from "../components/ui/PageLayout";
import { LandingPage } from "../pages/LandingPage";
import { OPERATOR } from "./operator";
import { api } from "../services/api";
import { setLang, t } from "../i18n";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  OPERATOR.brand = "Astra";
  setLang("de");
  vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "manual", online_payment: false });
  vi.spyOn(api, "getShopProducts").mockResolvedValue([]);
});
afterEach(() => { cleanup(); OPERATOR.brand = "Astra"; setLang("de"); localStorage.clear(); });

describe("Marke (OPERATOR.brand)", () => {
  it("Standard ist unverändert: Astra in Wortmarke, Tab-Titel und Texten", () => {
    const { container } = render(<Logo />);
    expect(container.textContent).toBe("Astra");
    expect(t("auth.login.title")).toBe("Astra Login");
    expect(t("nav.home")).toBe("Astra Startseite");
  });

  it("Astrahost erscheint in Logo-Wortmarke, Tab-Titel und i18n-Texten (DE/EN)", () => {
    OPERATOR.brand = "Astrahost";
    const { container } = render(<Logo />);
    expect(container.textContent).toBe("Astrahost");
    expect(t("auth.login.title")).toBe("Astrahost Login");
    expect(t("shop.payCardText")).toMatch(/Astrahost sieht keine Kartendaten/);
    setLang("en");
    expect(t("auth.login.title")).toBe("Astrahost Sign in");
    expect(t("boundary.updateText")).toMatch(/^Astrahost has been updated/);
  });

  it("Seitenrahmen setzt den Tab-Titel im Muster 'Seite · Marke'", async () => {
    OPERATOR.brand = "Astrahost";
    localStorage.setItem("astra_access_token", "t");
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "anna", is_admin: false } as never);
    render(<MemoryRouter><PageLayout title="Meine Server"><p>x</p></PageLayout></MemoryRouter>);
    await waitFor(() => expect(document.title).toBe("Meine Server · Astrahost"));
  });

  it("Landingpage zeigt die Marke in Titel, Kopf (Logo) und Fußzeile", async () => {
    OPERATOR.brand = "Astrahost";
    render(<MemoryRouter><LandingPage /></MemoryRouter>);
    expect(document.title).toBe("Astrahost – Game-Server mieten");
    expect(screen.getAllByLabelText("Astrahost").length).toBeGreaterThan(0);
    expect(document.body.textContent).toContain("Astrahost");
    expect(document.body.textContent).not.toMatch(/\bAstra\b(?!host)/);
  });
});
