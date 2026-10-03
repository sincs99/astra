// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { OrderNotice } from "./OrderNotice";
import { makeOrder } from "../test/fixtures";

afterEach(cleanup);

describe("OrderNotice", () => {
  it("warnt bei ueberfaelligen Bestellungen mit Sperrzeitpunkt und geplanter Loeschung", () => {
    render(<OrderNotice order={makeOrder({ status: "past_due", past_due_at: "2026-10-01T08:30:00", scheduled_deletion_at: "2026-10-08T08:30:00" })} />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/Gesperrt seit 1\.10\.2026 \d{2}:\d{2}/);
    expect(alert.textContent).toMatch(/Server wird am 8\.10\.2026 gelöscht/);
  });

  it("zeigt bei gekuendigten aktiven Bestellungen 'Läuft bis …, wird dann gelöscht'", () => {
    render(<OrderNotice order={makeOrder({ status: "active", cancel_at_period_end: true, scheduled_deletion_at: "2026-11-15T00:00:00", current_period_end: "2026-11-15T00:00:00" })} />);
    expect(screen.getByText("Läuft bis 15.11.2026, wird dann gelöscht")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("faellt ohne scheduled_deletion_at auf das Laufzeitende zurueck", () => {
    render(<OrderNotice order={makeOrder({ status: "active", cancel_at_period_end: true, scheduled_deletion_at: null, current_period_end: "2026-12-01T00:00:00" })} />);
    expect(screen.getByText(/Läuft bis 1\.12\.2026/)).toBeTruthy();
  });

  it.each(["active", "pending_payment", "cancelled", "expired", "awaiting_provisioning"] as const)("zeigt bei %s ohne Kuendigung nichts", (status) => {
    const { container } = render(<OrderNotice order={makeOrder({ status })} />);
    expect(container.textContent).toBe("");
  });
});
