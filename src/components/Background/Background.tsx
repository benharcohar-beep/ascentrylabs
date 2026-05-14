import { CircuitField } from "./CircuitField";
import "./background.css";

// Mission-control composition (clean, sparse, technical):
//   - dim base gradient
//   - two faint nebula gradients (kept for ambient depth, very low opacity)
//   - circuit-field network with traces, packets, hub pings
//   - vignette + scanlines + grid overlay
export function Background() {
  return (
    <div className="bg-root" aria-hidden>
      <div className="bg-base" />
      <div className="bg-nebula nebula-a" />
      <div className="bg-nebula nebula-b" />
      <CircuitField />
      <div className="bg-grid" />
      <div className="bg-vignette" />
      <div className="bg-scanline" />
    </div>
  );
}
