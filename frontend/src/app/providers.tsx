import { type ReactNode } from "react";

interface AppProvidersProps {
  children: ReactNode;
}

/**
 * Zentrale Provider-Komponente.
 * Hier können später QueryClient, ThemeProvider etc. eingehängt werden.
 */
export function AppProviders({ children }: AppProvidersProps) {
  return <>{children}</>;
}
