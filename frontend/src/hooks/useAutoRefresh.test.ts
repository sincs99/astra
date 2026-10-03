// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useAutoRefresh } from "./useAutoRefresh";

function setVisibility(state: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
}

describe("useAutoRefresh", () => {
  beforeEach(() => { vi.useFakeTimers(); setVisibility("visible"); });
  afterEach(() => { vi.useRealTimers(); });

  it("ruft den Callback im Intervall auf", () => {
    const cb = vi.fn();
    renderHook(() => useAutoRefresh(cb, 1000, true));
    vi.advanceTimersByTime(3000);
    expect(cb).toHaveBeenCalledTimes(3);
  });

  it("pausiert bei verstecktem Tab und holt beim Zurueckkehren sofort nach", () => {
    const cb = vi.fn();
    renderHook(() => useAutoRefresh(cb, 1000, true));
    setVisibility("hidden");
    vi.advanceTimersByTime(2000);
    expect(cb).not.toHaveBeenCalled();
    setVisibility("visible");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("tut nichts wenn deaktiviert und raeumt beim Unmount auf", () => {
    const cb = vi.fn();
    renderHook(() => useAutoRefresh(cb, 1000, false));
    vi.advanceTimersByTime(3000);
    expect(cb).not.toHaveBeenCalled();

    const cb2 = vi.fn();
    const { unmount } = renderHook(() => useAutoRefresh(cb2, 1000, true));
    unmount();
    vi.advanceTimersByTime(3000);
    expect(cb2).not.toHaveBeenCalled();
  });

  it("verwendet immer den neuesten Callback", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = renderHook(({ cb }) => useAutoRefresh(cb, 1000, true), { initialProps: { cb: first } });
    rerender({ cb: second });
    vi.advanceTimersByTime(1000);
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });
});
