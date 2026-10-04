import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppProviders } from "./app/providers";
import { AppRouter } from "./app/router";
import "./theme.css";
import { applyTheme, getThemePreference } from "./lib/theme";
import { ErrorBoundary } from "./components/ErrorBoundary";

applyTheme(getThemePreference());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProviders>
      <ErrorBoundary>
        <AppRouter />
      </ErrorBoundary>
    </AppProviders>
  </StrictMode>
);
