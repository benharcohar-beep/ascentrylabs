import { createRoot } from "react-dom/client";
import "./styles/globals.css";
import "./styles/app.css";
import App from "./App.tsx";

// Note: StrictMode intentionally omitted — @react-three/fiber 9.x has known
// "Invalid hook call" warnings under React 19 StrictMode that don't reflect
// real issues. Production builds never run StrictMode anyway.
createRoot(document.getElementById("root")!).render(<App />);
