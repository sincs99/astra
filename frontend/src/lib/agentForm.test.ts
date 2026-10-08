import { describe, expect, it } from "vitest";
import { EMPTY_AGENT_FORM, agentToForm, toAgentPayload, validPort } from "./agentForm";
import type { Agent } from "../services/api";

const valid = { ...EMPTY_AGENT_FORM, name: " Node1 ", fqdn: " n1.example.com " };

describe("validPort", () => {
  it.each([["1", 1], ["8080", 8080], ["65535", 65535]])("akzeptiert %s", (input, expected) => {
    expect(validPort(input)).toBe(expected);
  });
  it.each(["0", "65536", "-1", "1.5", "abc", ""])("lehnt '%s' ab", (input) => {
    expect(validPort(input)).toBeNull();
  });
});

describe("toAgentPayload", () => {
  it("trennt Connect- und Listen-Port", () => {
    const payload = toAgentPayload({ ...valid, connect: "443", listen: "8080" });
    expect(payload).toMatchObject({
      name: "Node1", fqdn: "n1.example.com", daemon_connect: 443, daemon_listen: 8080, daemon_sftp: 2022,
    });
  });

  it("meldet fehlende Pflichtfelder und ungueltige Ports als Text", () => {
    expect(toAgentPayload({ ...valid, name: "" })).toMatch(/erforderlich/);
    expect(toAgentPayload({ ...valid, connect: "0" })).toMatch(/Connect-Port/);
    expect(toAgentPayload({ ...valid, listen: "70000" })).toMatch(/Listen-Port/);
    expect(toAgentPayload({ ...valid, sftp: "x" })).toMatch(/SFTP-Port/);
  });

  it("uebernimmt Kapazitaet und Überallokation, 0 bedeutet kein Limit", () => {
    expect(toAgentPayload(valid)).toMatchObject({
      memory_total: 0, disk_total: 0, cpu_total: 0, memory_overalloc: 0, disk_overalloc: 0, cpu_overalloc: 0,
    });
    expect(toAgentPayload({ ...valid, memoryTotal: "16384", diskTotal: "500000", cpuTotal: "800", memoryOveralloc: "50", cpuOveralloc: "100" }))
      .toMatchObject({ memory_total: 16384, disk_total: 500000, cpu_total: 800, memory_overalloc: 50, cpu_overalloc: 100 });
  });

  it("verlangt beim Anlegen Arbeitsspeicher und Festplatte größer als 0, CPU bleibt optional", () => {
    const create = { requireCapacity: true };
    expect(toAgentPayload(valid, create)).toMatch(/Memory gesamt muss größer als 0/);
    expect(toAgentPayload({ ...valid, memoryTotal: "8192" }, create)).toMatch(/Disk gesamt muss größer als 0/);
    expect(toAgentPayload({ ...valid, memoryTotal: "8192", diskTotal: "100000" }, create)).toMatchObject({ memory_total: 8192, disk_total: 100000, cpu_total: 0 });
    // Beim Bearbeiten bleibt 0 erlaubt (ältere Agents ohne hinterlegte Kapazität)
    expect(toAgentPayload(valid)).toMatchObject({ memory_total: 0, disk_total: 0 });
  });

  it("lehnt ungueltige Kapazitaetswerte mit Meldung ab", () => {
    expect(toAgentPayload({ ...valid, memoryTotal: "-1" })).toMatch(/Memory gesamt/);
    expect(toAgentPayload({ ...valid, diskTotal: "1.5" })).toMatch(/Disk gesamt/);
    expect(toAgentPayload({ ...valid, cpuTotal: "x" })).toMatch(/CPU gesamt/);
    expect(toAgentPayload({ ...valid, memoryOveralloc: "1001" })).toMatch(/Memory-Überallokation/);
    expect(toAgentPayload({ ...valid, diskOveralloc: "-5" })).toMatch(/Disk-Überallokation/);
    expect(toAgentPayload({ ...valid, cpuOveralloc: "abc" })).toMatch(/CPU-Überallokation/);
  });

  it("nutzt Defaults für leeres Datenverzeichnis und ungueltige Upload-Groesse", () => {
    const payload = toAgentPayload({ ...valid, base: "  ", uploadSize: "-5" });
    expect(payload).toMatchObject({ daemon_base: "/var/lib/astra/volumes", upload_size: 100 });
  });
});

describe("agentToForm", () => {
  it("uebernimmt Agent-Werte und markiert Connect als manuell gesetzt", () => {
    const agent = {
      name: "N", fqdn: "f", scheme: "http", behind_proxy: true, daemon_connect: 443, daemon_listen: 8080,
      daemon_sftp: 2022, daemon_base: "/v", upload_size: 50, is_active: false,
      memory_total: 8192, disk_total: 100000, cpu_total: 400, memory_overalloc: 20, disk_overalloc: 0, cpu_overalloc: 50,
    } as Agent;
    expect(agentToForm(agent)).toMatchObject({
      connect: "443", listen: "8080", uploadSize: "50", isActive: false, behindProxy: true, connectTouched: true,
      memoryTotal: "8192", diskTotal: "100000", cpuTotal: "400", memoryOveralloc: "20", cpuOveralloc: "50",
    });
  });
});
