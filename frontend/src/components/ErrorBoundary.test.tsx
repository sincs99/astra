// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ErrorBoundary, isChunkLoadError } from "./ErrorBoundary";

afterEach(cleanup);

function Boom({ message }: { message: string }): never {
  throw new Error(message);
}

describe("ErrorBoundary", () => {
  it("erkennt fehlgeschlagene Chunk-Ladevorgaenge (Chrome, Firefox, Safari)", () => {
    expect(isChunkLoadError(new Error("Failed to fetch dynamically imported module: /assets/x.js"))).toBe(true);
    expect(isChunkLoadError(new Error("error loading dynamically imported module"))).toBe(true);
    expect(isChunkLoadError(new Error("Importing a module script failed."))).toBe(true);
    expect(isChunkLoadError(new Error("x is undefined"))).toBe(false);
  });

  it("zeigt bei Chunk-Fehler den Hinweis auf neue Version mit Reload-Button", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<ErrorBoundary><Boom message="Failed to fetch dynamically imported module: /a.js" /></ErrorBoundary>);
    expect(screen.getByText("Neue Version verfügbar")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Seite neu laden" })).toBeTruthy();
  });

  it("zeigt bei anderen Fehlern die allgemeine Meldung", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<ErrorBoundary><Boom message="kaputt" /></ErrorBoundary>);
    expect(screen.getByText("Etwas ist schiefgelaufen")).toBeTruthy();
  });
});
