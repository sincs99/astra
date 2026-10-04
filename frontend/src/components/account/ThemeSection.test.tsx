// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ThemeSection } from "./ThemeSection";
import { api } from "../../services/api";
import { getLang, setLang } from "../../i18n";

beforeEach(() => { vi.restoreAllMocks(); localStorage.clear(); localStorage.setItem("astra_access_token", "t"); setLang("de"); });
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

describe("ThemeSection Sprache", () => {
  it("zeigt den Hinweis zu Mails und Belegen und speichert die Auswahl am Konto", async () => {
    const update = vi.spyOn(api, "updateAccountLocale").mockResolvedValue({});
    render(<ThemeSection />);
    expect(screen.getByText(/Mails und Belege kommen in dieser Sprache/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Sprache"), { target: { value: "en" } });
    expect(getLang()).toBe("en");
    await waitFor(() => expect(update).toHaveBeenCalledWith("en"));
  });

  it("wechselt die Sprache auch, wenn das Backend das Feld nicht kennt", async () => {
    vi.spyOn(api, "updateAccountLocale").mockRejectedValue(new Error("404"));
    render(<ThemeSection />);
    fireEvent.change(screen.getByLabelText("Sprache"), { target: { value: "en" } });
    expect(getLang()).toBe("en");
  });
});
