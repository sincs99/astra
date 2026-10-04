// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ReceiptViewer, receiptFileName } from "./ReceiptViewer";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("ReceiptViewer", () => {
  it("bildet sichere Dateinamen", () => {
    expect(receiptFileName("R-2026-0001")).toBe("beleg-R-2026-0001.html");
    expect(receiptFileName("../x y")).toBe("beleg-.._x_y.html");
  });

  it("speichert den Beleg als HTML-Datei und schliesst per Button oder Hintergrund", () => {
    const create = vi.fn().mockReturnValue("blob:x");
    const revoke = vi.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const onClose = vi.fn();
    render(<ReceiptViewer number="R-1" html="<p>x</p>" onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Als Datei speichern" }));
    expect(create).toHaveBeenCalledTimes(1);
    expect((create.mock.calls[0][0] as Blob).type).toContain("text/html");
    expect(click).toHaveBeenCalled();
    expect(revoke).toHaveBeenCalledWith("blob:x");
    fireEvent.click(screen.getByRole("button", { name: "Schliessen" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
