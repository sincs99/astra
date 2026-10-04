// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RemindButton } from "./RemindButton";
import { api, ApiError } from "../../services/api";
import { setLang } from "../../i18n";

const order = { uuid: "o-1", id: 7, status: "active" } as const;

beforeEach(() => { vi.restoreAllMocks(); setLang("de"); });
afterEach(() => { cleanup(); setLang("de"); });

describe("RemindButton", () => {
  it("sendet die Erinnerung und meldet den Erfolg", async () => {
    const remind = vi.spyOn(api, "remindOrder").mockResolvedValue({ sent_at: "2026-10-05T10:00:00Z", kind: "renewal" });
    render(<RemindButton order={order} />);
    fireEvent.click(screen.getByRole("button", { name: "Erinnerung für Bestellung #7 senden" }));
    await waitFor(() => expect(remind).toHaveBeenCalledWith("o-1"));
    expect((await screen.findByRole("status")).textContent).toBe("Erinnerung gesendet");
  });

  it("zeigt bei 429 reminder_cooldown die Wartezeit in Stunden (aufgerundet)", async () => {
    vi.spyOn(api, "remindOrder").mockRejectedValue(new ApiError("zu früh", 429, "reminder_cooldown", { retry_after_seconds: 5400 }));
    render(<RemindButton order={order} />);
    fireEvent.click(screen.getByRole("button"));
    expect((await screen.findByRole("status")).textContent).toBe("Zuletzt vor kurzem gesendet, wieder möglich in 2 h");
    expect(screen.getByRole("button")).toBeTruthy();
  });

  it("blendet den Button bei 409 aus", async () => {
    vi.spyOn(api, "remindOrder").mockRejectedValue(new ApiError("nicht möglich", 409));
    render(<RemindButton order={order} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(screen.queryByRole("button")).toBeNull());
  });

  it("zeigt sonstige Fehler als Alert und bietet den Button weiter an", async () => {
    vi.spyOn(api, "remindOrder").mockRejectedValue(new ApiError("Server kaputt", 500));
    render(<RemindButton order={order} />);
    fireEvent.click(screen.getByRole("button"));
    expect((await screen.findByRole("alert")).textContent).toBe("Server kaputt");
    expect(screen.getByRole("button")).toBeTruthy();
  });

  it("erscheint nur für aktive, überfällige und auf Zahlung wartende Bestellungen", () => {
    for (const status of ["active", "past_due", "pending_payment"] as const) {
      const { unmount } = render(<RemindButton order={{ ...order, status }} />);
      expect(screen.getByRole("button")).toBeTruthy();
      unmount();
    }
    for (const status of ["cancelled", "refunded", "awaiting_provisioning"] as const) {
      const { unmount } = render(<RemindButton order={{ ...order, status }} />);
      expect(screen.queryByRole("button")).toBeNull();
      unmount();
    }
  });

  it("ist auf Englisch beschriftet", async () => {
    setLang("en");
    vi.spyOn(api, "remindOrder").mockResolvedValue({ sent_at: "x", kind: "renewal" });
    render(<RemindButton order={order} />);
    fireEvent.click(screen.getByRole("button", { name: "Send reminder for order #7" }));
    expect((await screen.findByRole("status")).textContent).toBe("Reminder sent");
  });
});
