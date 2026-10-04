import { Component, type ErrorInfo, type ReactNode } from "react";
import { btnPrimary } from "./ui";
import { t } from "../i18n";

interface Props { children: ReactNode }
interface State { error: Error | null }

/** Nach einem Deployment sind alte Chunk-Dateien weg: das Nachladen einer Seite schlägt dann fehl. */
export function isChunkLoadError(error: Error): boolean {
  return /dynamically imported module|Importing a module script failed|Loading chunk|error loading dynamically/i.test(error.message);
}

/** Fängt Render-Fehler ab, damit nicht die ganze App weiss wird. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unerwarteter UI-Fehler:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    if (isChunkLoadError(this.state.error)) {
      return (
        <div role="alert" style={{ maxWidth: 480, margin: "15vh auto", padding: 24, textAlign: "center" }}>
          <h1 style={{ fontSize: 22 }}>{t("boundary.updateTitle")}</h1>
          <p style={{ color: "var(--text)" }}>
            {t("boundary.updateText")}
          </p>
          <button style={btnPrimary} onClick={() => window.location.reload()}>{t("boundary.reload")}</button>
        </div>
      );
    }
    return (
      <div role="alert" style={{ maxWidth: 480, margin: "15vh auto", padding: 24, textAlign: "center" }}>
        <h1 style={{ fontSize: 22 }}>{t("boundary.title")}</h1>
        <p style={{ color: "var(--text)" }}>
          {t("boundary.text")}
        </p>
        <details style={{ margin: "12px 0", color: "var(--text-3)", fontSize: 13, textAlign: "left" }}>
          <summary style={{ cursor: "pointer" }}>{t("boundary.details")}</summary>
          <code style={{ display: "block", marginTop: 8, wordBreak: "break-word" }}>{this.state.error.message}</code>
        </details>
        <button style={btnPrimary} onClick={() => window.location.assign("/")}>
          {t("boundary.home")}
        </button>
      </div>
    );
  }
}
