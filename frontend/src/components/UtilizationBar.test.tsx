// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { UtilizationBar, formatMB, utilizationColor } from "./UtilizationBar";

afterEach(cleanup);

describe("UtilizationBar", () => {
  it("zeigt belegt von effektiv mit Progressbar", () => {
    render(<UtilizationBar label="Memory" used={2048} total={4096} percent={50} unit="MB" />);
    const bar = screen.getByRole("progressbar", { name: "Memory Auslastung" });
    expect(bar.getAttribute("aria-valuenow")).toBe("50");
    expect(screen.getByText("2.0 GB / 4.0 GB (50%)")).toBeTruthy();
  });

  it("kennzeichnet Agents ohne Kapazitaet als 'kein Limit'", () => {
    render(<UtilizationBar label="Disk" used={512} total={0} percent={0} unit="MB" />);
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.getByText("kein Limit")).toBeTruthy();
    expect(screen.getByText(/512 MB belegt/)).toBeTruthy();
  });

  it("begrenzt die Anzeige bei Ueberallokation auf 100 Prozent", () => {
    render(<UtilizationBar used={150} total={100} percent={150} unit="%" />);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("100");
  });
});

describe("Hilfsfunktionen", () => {
  it("formatiert MB und waehlt Schwellenfarben", () => {
    expect(formatMB(512)).toBe("512 MB");
    expect(formatMB(1536)).toBe("1.5 GB");
    expect(utilizationColor(10)).toBe("var(--ok)");
    expect(utilizationColor(75)).toBe("var(--warn)");
    expect(utilizationColor(95)).toBe("var(--danger)");
  });
});
