// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { api } from "../services/api";
import { setLang } from "../i18n";

import { AdminWebhooksPage } from "./AdminWebhooksPage";

const hook = { id: 3, uuid: "w-3", endpoint_url: "https://hook.example/a", description: "Slack", events: ["order.paid"], secret_token: "s3cr3t-token", is_active: true, created_at: null, updated_at: null };
const events = [{ event: "order.paid", description: "Paid" }, { event: "server.created", description: "Created" }];

function mount() {
  return render(<MemoryRouter><AdminWebhooksPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
  vi.spyOn(api, "getWebhookEvents").mockResolvedValue(events);
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

describe("AdminWebhooksPage", () => {
  it("listet Webhooks und gibt das Secret nie in aria-label oder title aus", async () => {
    vi.spyOn(api, "getWebhooks").mockResolvedValue([hook]);
    const { container } = mount();
    expect(await screen.findByText("https://hook.example/a")).toBeTruthy();
    expect(screen.getByText("Slack")).toBeTruthy();
    for (const el of container.querySelectorAll("[aria-label],[title]")) {
      expect(el.getAttribute("aria-label") ?? "").not.toContain("s3cr3t");
      expect(el.getAttribute("title") ?? "").not.toContain("s3cr3t");
    }
  });

  it("legt einen Webhook an", async () => {
    vi.spyOn(api, "getWebhooks").mockResolvedValue([]);
    const create = vi.spyOn(api, "createWebhook").mockResolvedValue(hook);
    mount();
    await screen.findByText("Noch keine Webhooks vorhanden.");
    fireEvent.change(screen.getByLabelText(/Endpoint-URL/), { target: { value: "https://x.example/h" } });
    fireEvent.click(screen.getByLabelText("order.paid"));
    fireEvent.click(screen.getByRole("button", { name: "Webhook erstellen" }));
    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ endpoint_url: "https://x.example/h", events: ["order.paid"] })));
    expect(await screen.findByText("Webhook erstellt.")).toBeTruthy();
  });

  it("verlangt mindestens ein Event", async () => {
    vi.spyOn(api, "getWebhooks").mockResolvedValue([]);
    const create = vi.spyOn(api, "createWebhook");
    mount();
    await screen.findByText("Noch keine Webhooks vorhanden.");
    fireEvent.change(screen.getByLabelText(/Endpoint-URL/), { target: { value: "https://x.example/h" } });
    fireEvent.click(screen.getByRole("button", { name: "Webhook erstellen" }));
    expect((await screen.findByRole("alert")).textContent).toContain("mindestens ein Event");
    expect(create).not.toHaveBeenCalled();
  });

  it("bearbeitet und löscht mit Bestätigung", async () => {
    vi.spyOn(api, "getWebhooks").mockResolvedValue([hook]);
    const update = vi.spyOn(api, "updateWebhook").mockResolvedValue(hook);
    const del = vi.spyOn(api, "deleteWebhook").mockResolvedValue(undefined as never);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Webhook https://hook.example/a bearbeiten" }));
    expect(screen.getByRole("heading", { name: "Webhook bearbeiten" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Webhook aktualisieren" }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(3, expect.objectContaining({ endpoint_url: "https://hook.example/a" })));
    fireEvent.click(screen.getByRole("button", { name: "Löschen" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith(3));
    expect(window.confirm).toHaveBeenCalledWith('Webhook "https://hook.example/a" löschen?');
  });

  it("löscht nicht, wenn die Bestätigung abgelehnt wird", async () => {
    vi.spyOn(api, "getWebhooks").mockResolvedValue([hook]);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const del = vi.spyOn(api, "deleteWebhook");
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Löschen" }));
    expect(del).not.toHaveBeenCalled();
  });

  it("zeigt Fehler beim Löschen als Hinweis", async () => {
    vi.spyOn(api, "getWebhooks").mockResolvedValue([hook]);
    vi.spyOn(api, "deleteWebhook").mockRejectedValue(new Error("nope"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Löschen" }));
    expect((await screen.findByRole("alert")).textContent).toBe("nope");
  });

  it("zeigt die Seite auf Englisch", async () => {
    setLang("en");
    vi.spyOn(api, "getWebhooks").mockResolvedValue([hook]);
    mount();
    expect(await screen.findByRole("heading", { name: "New webhook" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create webhook" })).toBeTruthy();
    // Die Liste kommt asynchron: erst auf den Zeilen-Button warten, dann die Spaltenüberschrift prüfen
    expect(await screen.findByRole("button", { name: "Send test to https://hook.example/a" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Actions" })).toBeTruthy();
  });
});
