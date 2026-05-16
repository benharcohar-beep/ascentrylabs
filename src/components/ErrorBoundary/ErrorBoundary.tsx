import { Component, type ErrorInfo, type ReactNode } from "react";
import "./error-boundary.css";

type Props = {
  children: ReactNode;
  /** Optional scope label shown in the fallback ("page", "section", etc.) */
  scope?: string;
};

type State = { error: Error | null; errorInfo: ErrorInfo | null };

// Catches render errors anywhere in the React tree below it and renders
// a branded fallback instead of a blank white screen. Two instances in
// the app:
//   1. Outer one in main.tsx wraps everything - catches catastrophic
//      crashes (full mission-control failure screen).
//   2. Inner one in App.tsx wraps just the <Routes> - catches page-level
//      crashes while keeping nav + footer + chat alive (smaller card,
//      "this page failed to load" with a back-to-home).
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, errorInfo: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary] caught render error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  reset = () => {
    this.setState({ error: null, errorInfo: null });
  };

  reload = () => {
    window.location.reload();
  };

  goHome = () => {
    window.location.href = "/";
  };

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <ErrorFallback
        error={this.state.error}
        scope={this.props.scope}
        onReset={this.reset}
        onReload={this.reload}
        onGoHome={this.goHome}
      />
    );
  }
}

type FallbackProps = {
  error: Error;
  scope?: string;
  onReset: () => void;
  onReload: () => void;
  onGoHome: () => void;
};

function ErrorFallback({ error, scope, onReset, onReload, onGoHome }: FallbackProps) {
  const isPageScope = scope === "page";
  return (
    <div className={`eb ${isPageScope ? "eb-inline" : "eb-full"}`} role="alert">
      <div className="eb-card">
        <div className="eb-corners" aria-hidden>
          <span /><span /><span /><span />
        </div>

        <header className="eb-head">
          <div className="eb-dot" aria-hidden />
          <span className="mono eb-eyebrow">SYSTEM · TRANSMISSION FAILURE</span>
        </header>

        <h1 className="eb-title">
          {isPageScope ? "This page failed to render." : "Something broke on the bridge."}
        </h1>

        <p className="eb-sub">
          {isPageScope
            ? "The rest of the site is still operational. Try reloading this page or head back home - the wireframe core is steady."
            : "An unexpected error took the site offline. Reload to retry, or go back to home. The error has been logged."}
        </p>

        <details className="eb-details">
          <summary className="mono">VIEW ERROR DETAIL</summary>
          <pre className="eb-pre">{error.name}: {error.message}{error.stack ? `\n\n${error.stack}` : ""}</pre>
        </details>

        <div className="eb-actions">
          {isPageScope && (
            <button type="button" className="btn btn-primary btn-fx" onClick={onReset}>
              <span className="btn-bracket">[</span>
              Retry render
              <span className="btn-bracket">]</span>
            </button>
          )}
          <button type="button" className="btn btn-primary btn-fx" onClick={onReload}>
            <span className="btn-bracket">[</span>
            Reload page
            <span className="btn-bracket">]</span>
          </button>
          <button type="button" className="btn btn-ghost btn-fx" onClick={onGoHome}>
            <span className="btn-bracket">[</span>
            Back to home
            <span className="btn-bracket">]</span>
          </button>
        </div>

        <footer className="eb-foot mono dim">
          ESCALATE · hunter@ascentrylabs.com
        </footer>
      </div>
    </div>
  );
}
