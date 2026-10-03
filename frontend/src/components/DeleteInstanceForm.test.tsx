// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DeleteInstanceForm } from "./DeleteInstanceForm";

afterEach(cleanup);

const typeName = (value: string) =>
  fireEvent.change(screen.getByLabelText(/Zur Bestätigung den Namen/), { target: { value } });
const deleteBtn = () => screen.getByRole("button", { name: "Endgültig löschen" }) as HTMLButtonElement;

describe("DeleteInstanceForm", () => {
  it("aktiviert Loeschen erst bei exakter Namenseingabe", async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<DeleteInstanceForm name="Mein Server" status="ready" onDelete={onDelete} onCancel={() => {}} />);
    expect(deleteBtn().disabled).toBe(true);
    typeName("mein server");
    expect(deleteBtn().disabled).toBe(true);
    typeName("Mein Server");
    expect(deleteBtn().disabled).toBe(false);
    fireEvent.click(deleteBtn());
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith(false));
  });

  it("zeigt den Fehler des Backends und erlaubt einen neuen Versuch", async () => {
    const onDelete = vi.fn().mockRejectedValue(new Error("Instance ist im Status 'restoring'"));
    render(<DeleteInstanceForm name="S" status="ready" onDelete={onDelete} onCancel={() => {}} />);
    typeName("S");
    fireEvent.click(deleteBtn());
    expect(await screen.findByText(/Status 'restoring'/)).toBeTruthy();
    expect(deleteBtn().disabled).toBe(false);
  });

  it("sperrt Kunden bei laufendem Vorgang mit Hinweis", () => {
    render(<DeleteInstanceForm name="S" status="provisioning" onDelete={vi.fn()} onCancel={() => {}} />);
    expect(screen.getByText(/Löschen ist erst danach möglich/)).toBeTruthy();
    typeName("S");
    expect(deleteBtn().disabled).toBe(true);
  });

  it("bietet Admins bei laufendem Vorgang 'Erzwingen' an und sendet force", async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<DeleteInstanceForm name="S" status="transferring" allowForce onDelete={onDelete} onCancel={() => {}} />);
    typeName("S");
    expect(deleteBtn().disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/Erzwingen/));
    expect(deleteBtn().disabled).toBe(false);
    fireEvent.click(deleteBtn());
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith(true));
  });

  it("zeigt den Zusatzhinweis zur laufenden Bestellung nur, wenn er uebergeben wird", () => {
    const { rerender } = render(<DeleteInstanceForm name="S" status="ready" onDelete={vi.fn()} onCancel={() => {}} />);
    expect(screen.queryByText(/Erstattung erfolgt nicht/)).toBeNull();
    rerender(<DeleteInstanceForm name="S" status="ready" notice="Die laufende Bestellung endet damit, eine Erstattung erfolgt nicht."
      onDelete={vi.fn()} onCancel={() => {}} />);
    expect(screen.getByText("Die laufende Bestellung endet damit, eine Erstattung erfolgt nicht.")).toBeTruthy();
  });

  it("blendet 'Erzwingen' ohne laufenden Vorgang aus", () => {
    render(<DeleteInstanceForm name="S" status="ready" allowForce onDelete={vi.fn()} onCancel={() => {}} />);
    expect(screen.queryByLabelText(/Erzwingen/)).toBeNull();
  });
});
