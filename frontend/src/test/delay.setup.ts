/**
 * Nur für `npm run test:slow` (vitest --mode slow): Mocks lösen verzögert auf, damit Ladephasen-Rennen in Tests sichtbar werden.
 * Jeder per `mockResolvedValue`/`mockResolvedValueOnce`/`mockRejectedValue`/`mockRejectedValueOnce` gesetzte Wert kommt erst nach
 * TEST_MOCK_DELAY_MS Millisekunden (Standard 30) an. Gilt für `vi.spyOn` und `vi.fn`; Mocks mit `mockImplementation(async …)` bleiben unverändert.
 */
import { vi } from "vitest";

const parsed = Number(process.env.TEST_MOCK_DELAY_MS);
const DELAY = Number.isFinite(parsed) && parsed >= 0 && process.env.TEST_MOCK_DELAY_MS ? parsed : 30;

type Spy = Record<string, unknown>;
type Impl = (f: (...a: unknown[]) => unknown) => unknown;

function delayed(spy: Spy): Spy {
  const later = <T,>(fn: () => T) =>
    new Promise<T>((resolve, reject) => setTimeout(() => { try { resolve(fn()); } catch (e) { reject(e); } }, DELAY));
  const impl = spy.mockImplementation as Impl;
  const implOnce = spy.mockImplementationOnce as Impl;
  spy.mockResolvedValue = (v: unknown) => impl.call(spy, () => later(() => v));
  spy.mockResolvedValueOnce = (v: unknown) => implOnce.call(spy, () => later(() => v));
  spy.mockRejectedValue = (e: unknown) => impl.call(spy, () => later(() => { throw e; }));
  spy.mockRejectedValueOnce = (e: unknown) => implOnce.call(spy, () => later(() => { throw e; }));
  return spy;
}

const originalSpyOn = vi.spyOn.bind(vi) as unknown as (...a: unknown[]) => Spy;
const originalFn = vi.fn.bind(vi) as unknown as (...a: unknown[]) => Spy;
(vi as unknown as { spyOn: unknown }).spyOn = (...args: unknown[]) => delayed(originalSpyOn(...args));
(vi as unknown as { fn: unknown }).fn = (...args: unknown[]) => delayed(originalFn(...args));
