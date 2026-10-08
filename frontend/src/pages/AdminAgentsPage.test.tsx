// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminAgentsPage } from "./AdminAgentsPage";
import { AdminAgentsMonitoringPage } from "./AdminAgentsMonitoringPage";
import { api, type Agent, type AgentMonitoringEntry, type Endpoint, type FleetSummary } from "../services/api";
import { setLang } from "../i18n";

const agent: Agent = {
  id: 1, uuid: "u1", name: "node-zh-01", fqdn: "node01.astra.dev", is_active: true, scheme: "https", behind_proxy: false,
  daemon_connect: 443, daemon_listen: 8080, daemon_sftp: 2022, daemon_base: "/var/lib/astra/volumes", upload_size: 100,
  memory_total: 8192, disk_total: 100000, cpu_total: 400, memory_overalloc: 0, disk_overalloc: 0, cpu_overalloc: 0,
  daemon_token_id: "tok-abc", has_daemon_credentials: true, last_seen_at: null, maintenance_mode: false, created_at: null, updated_at: null,
};
const endpoint: Endpoint = { id: 5, agent_id: 1, instance_id: null, ip: "0.0.0.0", port: 25565, is_locked: false, created_at: null, updated_at: null };

const mon: AgentMonitoringEntry = {
  id: 1, name: "node-zh-01", fqdn: "node01.astra.dev", health_status: "healthy", is_active: true, is_stale: false,
  last_seen_at: null, maintenance_mode: false, maintenance_reason: null, maintenance_started_at: null, available_for_deployment: true,
  capacity: { memory_total_mb: 8192, disk_total_mb: 100000, cpu_total_percent: 400, memory_overalloc_percent: 0, disk_overalloc_percent: 0, cpu_overalloc_percent: 0,
    effective_memory_mb: 8192, effective_disk_mb: 100000, effective_cpu_percent: 400 },
  utilization: { instance_count: 2, used_memory_mb: 4096, used_disk_mb: 1000, used_cpu_percent: 100, memory_utilization: 50, disk_utilization: 1, cpu_utilization: 25 },
  instance_count: 2, endpoint_summary: { total: 3, assigned: 1, free: 2, locked: 0 },
};
const fleet: FleetSummary = {
  total_agents: 1, healthy_agents: 1, stale_agents: 0, degraded_agents: 0, unreachable_agents: 0, total_instances: 2,
  total_memory_mb: 8192, used_memory_mb: 4096, memory_utilization: 50, total_disk_mb: 100000, used_disk_mb: 1000, disk_utilization: 1,
  total_cpu_percent: 400, used_cpu_percent: 100, cpu_utilization: 25, total_endpoints: 3, assigned_endpoints: 1,
};

const mountAgents = () => render(<MemoryRouter><AdminAgentsPage /></MemoryRouter>);
const mountMon = () => render(<MemoryRouter><AdminAgentsMonitoringPage /></MemoryRouter>);

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(api, "getAgentsMonitoring").mockResolvedValue([mon]);
  vi.spyOn(api, "getFleetSummary").mockResolvedValue(fleet);
});
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

describe("AdminAgentsPage", () => {
  it("listet Agents mit Endpoints und Auslastung", async () => {
    vi.spyOn(api, "getAgents").mockResolvedValue([agent]);
    vi.spyOn(api, "getEndpoints").mockResolvedValue([endpoint]);
    mountAgents();
    expect(await screen.findByRole("heading", { name: "node-zh-01" })).toBeTruthy();
    expect(screen.getByText("0.0.0.0:25565")).toBeTruthy();
    expect(screen.getByText("Frei")).toBeTruthy();
    expect(screen.getByText("tok-abc")).toBeTruthy();
    expect(await screen.findAllByRole("progressbar")).toHaveLength(3);
  });

  it("legt einen Agent an und laedt neu", async () => {
    const list = vi.spyOn(api, "getAgents").mockResolvedValue([]);
    vi.spyOn(api, "getEndpoints").mockResolvedValue([]);
    const create = vi.spyOn(api, "createAgent").mockResolvedValue(agent as never);
    mountAgents();
    expect(await screen.findByText("Noch keine Agents vorhanden.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Name *", { selector: "#new-name" }), { target: { value: "n1" } });
    fireEvent.change(screen.getByLabelText("FQDN *", { selector: "#new-fqdn" }), { target: { value: "n1.example.org" } });
    fireEvent.change(screen.getByLabelText("Arbeitsspeicher gesamt (MB) *", { selector: "#new-memory-total" }), { target: { value: "16384" } });
    fireEvent.change(screen.getByLabelText("Festplatte gesamt (MB) *", { selector: "#new-disk-total" }), { target: { value: "512000" } });
    fireEvent.click(screen.getByRole("button", { name: "Agent erstellen" }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0][0]).toMatchObject({ name: "n1", fqdn: "n1.example.org", memory_total: 16384, disk_total: 512000 });
    expect(await screen.findByText(/Agent erstellt/)).toBeTruthy();
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  });

  it("verlangt beim Anlegen Arbeitsspeicher und Festplatte (> 0) und erklärt, wofür sie dienen", async () => {
    vi.spyOn(api, "getAgents").mockResolvedValue([]);
    vi.spyOn(api, "getEndpoints").mockResolvedValue([]);
    const create = vi.spyOn(api, "createAgent").mockResolvedValue(agent as never);
    mountAgents();
    await screen.findByText("Noch keine Agents vorhanden.");
    expect(screen.getByText(/Kapazitätsplanung \(automatische Platzierung neuer Server\)/)).toBeTruthy();
    const memory = screen.getByLabelText("Arbeitsspeicher gesamt (MB) *", { selector: "#new-memory-total" }) as HTMLInputElement;
    expect(memory.required).toBe(true);
    expect(memory.value).toBe("");
    fireEvent.change(screen.getByLabelText("Name *", { selector: "#new-name" }), { target: { value: "n1" } });
    fireEvent.change(screen.getByLabelText("FQDN *", { selector: "#new-fqdn" }), { target: { value: "n1.example.org" } });
    fireEvent.change(memory, { target: { value: "0" } });
    fireEvent.submit(memory.closest("form") as HTMLFormElement);
    expect(await screen.findByText(/Memory gesamt muss größer als 0 sein/)).toBeTruthy();
    fireEvent.change(memory, { target: { value: "8192" } });
    fireEvent.submit(memory.closest("form") as HTMLFormElement);
    expect(await screen.findByText(/Disk gesamt muss größer als 0 sein/)).toBeTruthy();
    expect(create).not.toHaveBeenCalled();
  });

  it("kennzeichnet beim Bearbeiten eine fehlende Kapazität (0) mit Hinweis, erlaubt aber das Speichern", async () => {
    vi.spyOn(api, "getAgents").mockResolvedValue([{ ...agent, memory_total: 0, disk_total: 100000 } as never]);
    vi.spyOn(api, "getEndpoints").mockResolvedValue([]);
    mountAgents();
    fireEvent.click(await screen.findByRole("button", { name: /bearbeiten/i }));
    const memory = await screen.findByLabelText("Arbeitsspeicher gesamt (MB)", { selector: "#edit-memory-total" });
    expect((memory as HTMLInputElement).required).toBe(false);
    expect(screen.getAllByText(/Noch nicht hinterlegt/)).toHaveLength(1);
  });

  it("rotiert Credentials nach Bestaetigung", async () => {
    vi.spyOn(api, "getAgents").mockResolvedValue([agent]);
    vi.spyOn(api, "getEndpoints").mockResolvedValue([]);
    const rotate = vi.spyOn(api, "rotateAgentCredentials").mockResolvedValue({ message: "Rotiert", agent } as never);
    mountAgents();
    fireEvent.click(await screen.findByRole("button", { name: "Credentials rotieren" }));
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expect(rotate).toHaveBeenCalledWith(1));
    expect(await screen.findByText("Rotiert")).toBeTruthy();
  });

  it("zeigt die config.yml und kopiert sie ohne Secret im aria-label", async () => {
    vi.spyOn(api, "getAgents").mockResolvedValue([agent]);
    vi.spyOn(api, "getEndpoints").mockResolvedValue([]);
    vi.spyOn(api, "getAgentConfiguration").mockResolvedValue({ yaml: "token: SECRET-VALUE" } as never);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    mountAgents();
    fireEvent.click(await screen.findByRole("button", { name: "config.yml von node-zh-01 anzeigen" }));
    expect(await screen.findByText("token: SECRET-VALUE")).toBeTruthy();
    const copy = screen.getByRole("button", { name: "config.yml in die Zwischenablage kopieren" });
    expect(copy.getAttribute("aria-label")).not.toContain("SECRET");
    fireEvent.click(copy);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("token: SECRET-VALUE"));
  });

  it("legt einen Endpoint-Bereich an", async () => {
    vi.spyOn(api, "getAgents").mockResolvedValue([agent]);
    vi.spyOn(api, "getEndpoints").mockResolvedValue([]);
    const bulk = vi.spyOn(api, "createEndpointsBulk").mockResolvedValue({ created: 3, skipped: 1 } as never);
    mountAgents();
    await screen.findByRole("heading", { name: "node-zh-01" });
    fireEvent.change(screen.getByLabelText("Agent *"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Port oder Bereich *"), { target: { value: "25565-25567" } });
    fireEvent.click(screen.getByRole("button", { name: "Endpoint(s) erstellen" }));
    await waitFor(() => expect(bulk).toHaveBeenCalledWith(1, { ip: "0.0.0.0", port_start: 25565, port_end: 25567 }));
    expect(await screen.findByText("3 angelegt, 1 übersprungen.")).toBeTruthy();
  });

  it("zeigt Ladefehler als Alert", async () => {
    vi.spyOn(api, "getAgents").mockRejectedValue(new Error("Backend down"));
    vi.spyOn(api, "getEndpoints").mockResolvedValue([]);
    mountAgents();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Backend down")).toBeTruthy();
  });

  it("zeigt die Seite auf Englisch", async () => {
    setLang("en");
    vi.spyOn(api, "getAgents").mockResolvedValue([agent]);
    vi.spyOn(api, "getEndpoints").mockResolvedValue([endpoint]);
    mountAgents();
    expect(await screen.findByRole("button", { name: "Rotate credentials" })).toBeTruthy();
    expect(screen.getByText("New endpoint")).toBeTruthy();
    expect(screen.getByText("Free")).toBeTruthy();
  });
});

describe("AdminAgentsMonitoringPage", () => {
  it("zeigt bei fehlender Kapazität (0) einen klaren Hinweis statt '0 %'; CPU bleibt 'kein Limit'", async () => {
    const noCapacity: AgentMonitoringEntry = {
      ...mon,
      capacity: { ...mon.capacity, memory_total_mb: 0, disk_total_mb: 0, effective_memory_mb: 0, effective_disk_mb: 0, cpu_total_percent: 0, effective_cpu_percent: 0 },
      utilization: { ...mon.utilization, memory_utilization: 0, disk_utilization: 0, cpu_utilization: 0, used_cpu_percent: 0 },
    };
    vi.spyOn(api, "getAgentsMonitoring").mockResolvedValue([noCapacity]);
    mountMon();
    expect(await screen.findAllByText(/Kapazität nicht hinterlegt/)).toHaveLength(2);
    expect(screen.getByText("kein Limit")).toBeTruthy();
    expect(screen.queryByText(/\(0 %\)/)).toBeNull();
  });

  it("listet Agents mit Kennzahlen", async () => {
    vi.spyOn(api, "getAgentsMonitoring").mockResolvedValue([mon]);
    mountMon();
    expect(await screen.findByText("node-zh-01")).toBeTruthy();
    expect(screen.getByText("node01.astra.dev")).toBeTruthy();
    expect(screen.getByRole("group", { name: "Flottenübersicht" })).toBeTruthy();
    expect(screen.getByText("1/3")).toBeTruthy();
  });

  it("aktiviert die Wartung nach Bestaetigung mit Grund", async () => {
    vi.spyOn(window, "prompt").mockReturnValue("Update");
    const enable = vi.spyOn(api, "enableAgentMaintenance").mockResolvedValue({} as never);
    mountMon();
    fireEvent.click(await screen.findByRole("button", { name: "Wartung aktivieren" }));
    await waitFor(() => expect(enable).toHaveBeenCalledWith(1, { reason: "Update" }));
  });

  it("beendet die Wartung", async () => {
    vi.spyOn(api, "getAgentsMonitoring").mockResolvedValue([{ ...mon, maintenance_mode: true }]);
    const disable = vi.spyOn(api, "disableAgentMaintenance").mockResolvedValue({} as never);
    mountMon();
    fireEvent.click(await screen.findByRole("button", { name: "Wartung beenden" }));
    await waitFor(() => expect(disable).toHaveBeenCalledWith(1));
  });

  it("zeigt Fehler als Alert", async () => {
    vi.spyOn(api, "getAgentsMonitoring").mockRejectedValue(new Error("kaputt"));
    mountMon();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/kaputt/)).toBeTruthy();
  });

  it("zeigt die Seite auf Englisch", async () => {
    setLang("en");
    mountMon();
    expect(await screen.findByRole("button", { name: "Enable maintenance" })).toBeTruthy();
    expect(screen.getByLabelText("Status filter")).toBeTruthy();
    expect(screen.getByText("Fleet monitoring")).toBeTruthy();
  });
});
