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

  it("zeigt bei erstatteten Bestellungen Erstattung und geplante Loeschung", () => {
    render(<OrderNotice order={makeOrder({ status: "refunded", refunded_at: "2026-10-02T09:00:00Z", scheduled_deletion_at: "2026-10-09T09:00:00Z" })} />);
    expect(screen.getByRole("alert").textContent).toBe("Zahlung erstattet am 2.10.2026, der Server wird am 9.10.2026 gelöscht");
  });

  it("zeigt ohne Loeschtermin, dass der Server gesperrt ist", () => {
    render(<OrderNotice order={makeOrder({ status: "refunded", scheduled_deletion_at: null })} />);
    expect(screen.getByRole("alert").textContent).toBe("Zahlung erstattet, der Server ist gesperrt");
  });

  it("zeigt bei angefochtener Zahlung ein Badge, auch bei laufender Bestellung", () => {
    render(<OrderNotice order={makeOrder({ status: "active", disputed: true })} />);
    expect(screen.getByRole("status", { name: "Zahlung angefochten" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it.each(["active", "pending_payment", "cancelled", "expired", "awaiting_provisioning"] as const)("zeigt bei %s ohne Kuendigung nichts", (status) => {
    const { container } = render(<OrderNotice order={makeOrder({ status })} />);
    expect(container.textContent).toBe("");
  });
});
