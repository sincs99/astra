// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AgbPage, DatenschutzPage, ImpressumPage } from "./LegalPages";
import { ProtectedRoute } from "../app/router";
import { OPERATOR } from "../legal/operator";
import { setLang } from "../i18n";
import { Route, Routes } from "react-router-dom";

beforeEach(() => { localStorage.clear(); OPERATOR.jurisdiction = "DE"; setLang("de"); });
afterEach(() => { cleanup(); OPERATOR.jurisdiction = "DE"; setLang("de"); });

const mount = (ui: React.ReactElement, path = "/") => render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);

describe("Rechtsseiten", () => {
  it.each([
    ["Impressum", <ImpressumPage />, /Anbieter/],
    ["Datenschutzerklärung", <DatenschutzPage />, /Verantwortlicher/],
    ["Allgemeine Geschäftsbedingungen", <AgbPage />, /Geltungsbereich/],
  ])("%s ist ohne Login sichtbar, mit Hinweis und Platzhaltern", (title, element, section) => {
    mount(element);
    expect(screen.getByRole("heading", { level: 1, name: title })).toBeTruthy();
    expect(screen.getByRole("note").textContent).toMatch(/Vom Betreiber auszufüllen/);
    expect(screen.getByRole("note").textContent).toMatch(/keine Rechtsberatung/);
    expect(screen.getByText(section)).toBeTruthy();
    expect(screen.getAllByText("[vom Betreiber auszufüllen]").length).toBeGreaterThan(0);
  });

  it("hebt offene Platzhalter hervor", () => {
    mount(<ImpressumPage />);
    const marks = document.querySelectorAll("mark");
    expect(marks.length).toBeGreaterThan(5);
    expect(marks[0].textContent).toBe("[vom Betreiber auszufüllen]");
  });

  it("verlinkt im Footer alle drei Rechtsseiten", () => {
    mount(<AgbPage />);
    const nav = within(screen.getByRole("navigation", { name: "Rechtliches" }));
    expect(nav.getByRole("link", { name: "Impressum" }).getAttribute("href")).toBe("/impressum");
    expect(nav.getByRole("link", { name: "Datenschutz" }).getAttribute("href")).toBe("/datenschutz");
    expect(nav.getByRole("link", { name: "AGB" }).getAttribute("href")).toBe("/agb");
  });

  it("beschreibt den lokalen Speicher ehrlich (Token und Einstellungen, kein Tracking)", () => {
    mount(<DatenschutzPage />);
    expect(screen.getByText(/Anmelde-Token/)).toBeTruthy();
  });
});

describe("Rechtsraum (DE/CH)", () => {
  it("DE (Standard): Impressum, Widerrufsrecht in den AGB, Aufsichtsbehörde statt EDÖB", () => {
    mount(<ImpressumPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Impressum" })).toBeTruthy();
    expect(screen.getByText(/Vertretungsberechtigt/)).toBeTruthy();
    cleanup();
    mount(<AgbPage />);
    expect(screen.getByText("8. Widerrufsrecht")).toBeTruthy();
    expect(screen.queryByText(/kein allgemeines Widerrufsrecht/)).toBeNull();
    cleanup();
    mount(<DatenschutzPage />);
    expect(screen.queryByText(/EDÖB/)).toBeNull();
    expect(screen.queryByText(/DSG/)).toBeNull();
    expect(screen.getByText(/zuständigen Aufsichtsbehörde/)).toBeTruthy();
  });

  it("CH: Anbieterkennzeichnung nach UWG ohne TMG/DDG-Bezüge", () => {
    OPERATOR.jurisdiction = "CH";
    mount(<ImpressumPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Anbieterkennzeichnung / Kontakt" })).toBeTruthy();
    expect(screen.getByText(/Art\. 3 Abs\. 1 lit\. s/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/TMG|DDG|Telemediengesetz|§ 5/);
    expect(screen.queryByText(/Vertretungsberechtigt/)).toBeNull();
  });

  it("CH: Datenschutz nach DSG mit Rechten, EDÖB und DSGVO-Hinweis für EU-Kunden", () => {
    OPERATOR.jurisdiction = "CH";
    mount(<DatenschutzPage />);
    expect(screen.getByText(/Bundesgesetz über den Datenschutz \(DSG/)).toBeTruthy();
    expect(screen.getByText(/Eidgenössischen Datenschutz- und Öffentlichkeitsbeauftragten \(EDÖB\)/)).toBeTruthy();
    expect(screen.getByText("8. Kunden in der EU")).toBeTruthy();
    expect(screen.getByText(/gilt zusätzlich die DSGVO/)).toBeTruthy();
    expect(screen.getByText(/Cloudflare Turnstile oder hCaptcha/)).toBeTruthy();
    expect(screen.getByText(/Art\. 958f OR/)).toBeTruthy();
  });

  it("CH: AGB mit Schweizer Recht, Gerichtsstand und ohne Widerrufsrecht (Leistungsbeginn sofort)", () => {
    OPERATOR.jurisdiction = "CH";
    mount(<AgbPage />);
    expect(screen.getByText("8. Leistungsbeginn, kein Widerrufsrecht")).toBeTruthy();
    expect(screen.getByText(/kein allgemeines Widerrufsrecht/)).toBeTruthy();
    expect(screen.getByText(/Es gilt Schweizer Recht/)).toBeTruthy();
    expect(screen.getByText("9. Anwendbares Recht und Gerichtsstand")).toBeTruthy();
    expect(screen.queryByText("8. Widerrufsrecht")).toBeNull();
  });

  it("zeigt die Texte beider Rechtsräume auf Englisch", () => {
    setLang("en");
    mount(<AgbPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Terms and conditions" })).toBeTruthy();
    expect(screen.getByText("8. Right of withdrawal")).toBeTruthy();
    expect(screen.getByRole("note").textContent).toMatch(/not legal\s+advice/);
    cleanup();
    OPERATOR.jurisdiction = "CH";
    mount(<AgbPage />);
    expect(screen.getByText("8. Start of service, no right of withdrawal")).toBeTruthy();
    cleanup();
    mount(<DatenschutzPage />);
    expect(screen.getByText(/FDPIC \/ EDÖB/)).toBeTruthy();
    cleanup();
    mount(<ImpressumPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Provider identification / contact" })).toBeTruthy();
  });
});

describe("Optionale Betreiberangaben", () => {
  const OPTIONAL = ["legalForm", "phone", "representative", "register", "vatId", "supervisoryAuthority", "hosting", "paymentProvider"] as const;
  const snapshot = { ...OPERATOR };
  const fill = () => {
    Object.assign(OPERATOR, { name: "Max Muster", legalForm: "Einzelunternehmen", street: "Hauptstr. 1", zipCity: "8000 Zürich", country: "Schweiz", email: "hi@example.ch", lastUpdated: "Oktober 2026", phone: "+41 44 000 00 00", representative: "Max Muster", register: "CHE-123", vatId: "CHE-123.456.789 MWST", supervisoryAuthority: "Behörde X", hosting: "Hoster AG", paymentProvider: "Stripe" });
  };
  const clearOptional = () => { for (const key of OPTIONAL) OPERATOR[key] = ""; };
  afterEach(() => Object.assign(OPERATOR, snapshot));

  it("CH: leere Angaben verschwinden samt Beschriftung, gefüllte bleiben", () => {
    OPERATOR.jurisdiction = "CH";
    fill();
    clearOptional();
    mount(<ImpressumPage />);
    expect(screen.getByText(/Max Muster/)).toBeTruthy();
    expect(screen.queryByText(/Telefon/)).toBeNull();
    expect(screen.queryByText("Register und Steuern")).toBeNull();
    expect(screen.queryByText(/MWST/)).toBeNull();
    expect(document.body.textContent).not.toMatch(/\(\)/);
    expect(document.body.textContent).not.toContain("[vom Betreiber auszufüllen]");
    cleanup();
    mount(<DatenschutzPage />);
    expect(screen.queryByText(/Hosting:/)).toBeNull();
    expect(screen.queryByText(/Zahlungsabwicklung:/)).toBeNull();
    cleanup();
    mount(<AgbPage />);
    expect(screen.queryByText(/Zahlungsanbieter/)).toBeNull();
  });

  it("CH: gefüllte optionale Angaben erscheinen mit Beschriftung", () => {
    OPERATOR.jurisdiction = "CH";
    fill();
    mount(<ImpressumPage />);
    expect(screen.getByText(/Telefon/)).toBeTruthy();
    expect(screen.getByText("Register und Steuern")).toBeTruthy();
    expect(document.body.textContent).toContain("CHE-123.456.789 MWST");
    expect(document.body.textContent).toContain("Max Muster (Einzelunternehmen)");
  });

  it("DE: leere Angaben (Telefon, Vertretung, Register, USt-IdNr., Aufsichtsbehörde) werden ausgelassen", () => {
    fill();
    clearOptional();
    mount(<ImpressumPage />);
    expect(screen.queryByText(/Telefon/)).toBeNull();
    expect(screen.queryByText("Vertretungsberechtigt")).toBeNull();
    expect(screen.queryByText("Register und Steuern")).toBeNull();
    cleanup();
    mount(<DatenschutzPage />);
    expect(screen.queryByText(/zuständigen Aufsichtsbehörde/)).toBeNull();
    expect(screen.getByText("7. Deine Rechte")).toBeTruthy();
  });

  it("Platzhalter bleiben sichtbar und hervorgehoben (nur \"\" blendet aus)", () => {
    OPERATOR.jurisdiction = "CH";
    mount(<ImpressumPage />);
    expect(screen.getByText(/Telefon/)).toBeTruthy();
    expect(document.querySelectorAll("mark").length).toBeGreaterThan(4);
  });
});

describe("ProtectedRoute", () => {
  function app(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route path="/shop" element={<ProtectedRoute><div>Geheim</div></ProtectedRoute>} />
        </Routes>
      </MemoryRouter>,
    );
  }
  function LoginProbe() {
    return <div>Login: {window.location.pathname}</div>;
  }

  it("leitet ausgeloggte Nutzer zum Login und merkt sich das Ziel", () => {
    const { container } = app("/shop?x=1");
    expect(container.textContent).toContain("Login");
    expect(container.textContent).not.toContain("Geheim");
  });

  it("zeigt eingeloggten Nutzern die Seite", () => {
    localStorage.setItem("astra_access_token", "t");
    app("/shop");
    expect(screen.getByText("Geheim")).toBeTruthy();
  });
});
