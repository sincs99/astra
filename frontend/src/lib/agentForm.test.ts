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

  it("nutzt Defaults fuer leeres Datenverzeichnis und ungueltige Upload-Groesse", () => {
    const payload = toAgentPayload({ ...valid, base: "  ", uploadSize: "-5" });
    expect(payload).toMatchObject({ daemon_base: "/var/lib/pterodactyl/volumes", upload_size: 100 });
  });
});

describe("agentToForm", () => {
  it("uebernimmt Agent-Werte und markiert Connect als manuell gesetzt", () => {
    const agent = {
      name: "N", fqdn: "f", scheme: "http", behind_proxy: true, daemon_connect: 443, daemon_listen: 8080,
      daemon_sftp: 2022, daemon_base: "/v", upload_size: 50, is_active: false,
    } as Agent;
    expect(agentToForm(agent)).toMatchObject({
      connect: "443", listen: "8080", uploadSize: "50", isActive: false, behindProxy: true, connectTouched: true,
    });
  });
});
