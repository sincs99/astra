import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppProviders } from "./app/providers";
import { AppRouter } from "./app/router";
import "@fontsource/geist/400.css";
import "@fontsource/geist/500.css";
import "@fontsource/geist/600.css";
import "@fontsource/geist-mono/400.css";
import "@fontsource/geist-mono/500.css";
import "./theme.css";
import { applyTheme, getThemePreference, watchSystemTheme } from "./lib/theme";
import { LangRoot } from "./i18n/LangRoot";
import { initLang } from "./i18n";
import { ErrorBoundary } from "./components/ErrorBoundary";

applyTheme(getThemePreference());
watchSystemTheme();
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
