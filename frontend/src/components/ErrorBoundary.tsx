import { Component, type ErrorInfo, type ReactNode } from "react";
import { btnPrimary } from "./ui";

interface Props { children: ReactNode }
interface State { error: Error | null }

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
    return (
      <div role="alert" style={{ maxWidth: 480, margin: "15vh auto", padding: 24, textAlign: "center" }}>
        <h1 style={{ fontSize: 22 }}>Etwas ist schiefgelaufen</h1>
        <p style={{ color: "#444" }}>
          Das tut uns leid. Bitte lade die Seite neu oder gehe zur Startseite. Wenn das Problem bleibt,
          melde dich beim Support und nenne die technischen Details unten.
        </p>
        <details style={{ margin: "12px 0", color: "#666", fontSize: 13, textAlign: "left" }}>
          <summary style={{ cursor: "pointer" }}>Technische Details</summary>
          <code style={{ display: "block", marginTop: 8, wordBreak: "break-word" }}>{this.state.error.message}</code>
        </details>
        <button style={btnPrimary} onClick={() => window.location.assign("/")}>
          Zur Startseite
        </button>
      </div>
    );
  }
}
