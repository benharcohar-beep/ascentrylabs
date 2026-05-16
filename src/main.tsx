import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./styles/globals.css";
import "./styles/app.css";
import App from "./App.tsx";
import { ErrorBoundary } from "./components/ErrorBoundary/ErrorBoundary";

// Outer ErrorBoundary catches catastrophic crashes (full takeover
// mission-control failure screen). An inner one in App.tsx wraps the
// <Routes> for per-page recovery.
//
// StrictMode intentionally omitted — @react-three/fiber 9.x has known
// "Invalid hook call" warnings under React 19 StrictMode that don't reflect
// real issues. Production builds never run StrictMode anyway.
createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </ErrorBoundary>
);
