import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppProviders } from "./app/providers";
import { AppRouter } from "./app/router";
import "./theme.css";
import { applyTheme, getThemePreference } from "./lib/theme";
import { LangRoot } from "./i18n/LangRoot";
import { initLang } from "./i18n";
import { ErrorBoundary } from "./components/ErrorBoundary";

applyTheme(getThemePreference());
initLang();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProviders>
      <LangRoot>
        <ErrorBoundary>
          <AppRouter />
        </ErrorBoundary>
      </LangRoot>
    </AppProviders>
  </StrictMode>
);
