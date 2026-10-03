// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SftpAccess } from "./SftpAccess";
import { api, type Instance } from "../services/api";

const base = {
  uuid: "0f3a9c1e-aaaa-bbbb-cccc-ddddeeeeffff",
  agent_id: 7,
  connection: { host: "n1.example.com", ip: "1.2.3.4", port: 25565, address: "n1.example.com:25565" },
} as Instance;

function renderBox(instance: Instance) {
  return render(<MemoryRouter><SftpAccess instance={instance} /></MemoryRouter>);
}

describe("SftpAccess", () => {
  beforeEach(() => { vi.restoreAllMocks(); });
  afterEach(() => { cleanup(); });

  it("zeigt Host, Port aus connection.sftp_port und den Benutzernamen", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "alice", is_admin: false } as never);
    const agents = vi.spyOn(api, "getAgents");
    renderBox({ ...base, connection: { ...base.connection!, sftp_port: 2022 } });
    expect(await screen.findByText("alice.0f3a9c1e")).toBeTruthy();
    expect(screen.getByText("n1.example.com")).toBeTruthy();
    expect(screen.getByText("2022")).toBeTruthy();
    expect(screen.getByRole("link", { name: /SSH-Keys/ }).getAttribute("href")).toBe("/account/ssh-keys");
    expect(agents).not.toHaveBeenCalled();
  });

  it("lädt den Port für Admins aus der Agent-Liste, wenn das Backend ihn nicht liefert", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
    vi.spyOn(api, "getAgents").mockResolvedValue([{ id: 7, daemon_sftp: 2222 }] as never);
    renderBox(base);
    expect(await screen.findByText("2222")).toBeTruthy();
  });

  it("laesst die Port-Zeile für Kunden ohne bekannten Port weg", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
    renderBox(base);
    expect(await screen.findByText("bob.0f3a9c1e")).toBeTruthy();
    expect(screen.queryByText("Port")).toBeNull();
  });

  it("rendert nichts ohne Host", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
    const { container } = renderBox({ ...base, connection: null });
    await Promise.resolve();
    expect(container.textContent).toBe("");
  });
});
