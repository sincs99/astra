// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { FlashBanner } from "./FlashBanner";
import { setFlash, takeFlash } from "../lib/flash";

beforeEach(() => sessionStorage.clear());
afterEach(cleanup);

const mount = () => render(<MemoryRouter><FlashBanner /></MemoryRouter>);

describe("FlashBanner", () => {
  it("zeigt nichts ohne Hinweis", () => {
    const { container } = mount();
    expect(container.textContent).toBe("");
  });

  it("zeigt den Hinweis einmal mit Link und kann geschlossen werden", () => {
    setFlash({ kind: "warning", text: "Nur noch 1 übrig.", link: { to: "/account", label: "Zum Konto" } });
    mount();
    expect(screen.getByRole("alert").textContent).toContain("Nur noch 1 übrig.");
    expect(screen.getByRole("link", { name: "Zum Konto" }).getAttribute("href")).toBe("/account");
    expect(takeFlash()).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Schliessen" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("verwirft kaputte Eintraege", () => {
    sessionStorage.setItem("astra_flash", "{nicht-json");
    const { container } = mount();
    expect(container.textContent).toBe("");
  });
});
