import type { Instance, InstanceEndpoint } from "../services/api";

/** Host fuer Verbindungsadressen: FQDN des Agents, sonst die IP des Endpoints. */
export function endpointHost(inst: Instance, ep: InstanceEndpoint): string {
  return inst.connection?.host || ep.ip;
}

export function endpointAddress(inst: Instance, ep: InstanceEndpoint): string {
  return `${endpointHost(inst, ep)}:${ep.port}`;
}

/** Primaerer Endpoint zuerst, danach die uebrigen in der gelieferten Reihenfolge. */
export function sortedEndpoints(inst: Instance): InstanceEndpoint[] {
  const list = inst.endpoints ?? [];
  return [...list.filter((e) => e.is_primary), ...list.filter((e) => !e.is_primary)];
}

export function extraEndpoints(inst: Instance): InstanceEndpoint[] {
  return sortedEndpoints(inst).filter((e) => !e.is_primary);
}
