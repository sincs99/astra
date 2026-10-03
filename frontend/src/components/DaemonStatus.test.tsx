// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { DaemonStatus } from "./DaemonStatus";

afterEach(cleanup);

describe("DaemonStatus", () => {
  it("rendert nichts ohne Daemon-Pruefung", () => {
    const { container } = render(<DaemonStatus />);
    expect(container.textContent).toBe("");
    cleanup();
    expect(render(<DaemonStatus daemon_reachable={null} />).container.textContent).toBe("");
  });

  it("zeigt erreichbar mit Version", () => {
    render(<DaemonStatus daemon_reachable daemon_version="1.11.13" />);
    expect(screen.getByLabelText("Wings erreichbar")).toBeTruthy();
    expect(screen.getByText("Wings 1.11.13")).toBeTruthy();
  });

  it("zeigt nicht erreichbar mit dem Fehler als Tooltip", () => {
    render(<DaemonStatus daemon_reachable={false} daemon_error="Connection refused" />);
    const badge = screen.getByLabelText("Wings nicht erreichbar");
    expect(badge.closest("[title]")?.getAttribute("title")).toBe("Connection refused");
  });
});
