// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AgbPage, DatenschutzPage, ImpressumPage } from "./LegalPages";
import { ProtectedRoute } from "../app/router";
import { Route, Routes } from "react-router-dom";

beforeEach(() => localStorage.clear());
afterEach(cleanup);

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
