import { lazy, Suspense } from "react";
import "./background.css";

// Composition for the "AI factory" mood (clean, mission-control):
//   - dim base gradient
//   - two faint nebula gradients (kept for ambient depth, very low opacity)
//   - articulated 3D robotic arms (Three.js + R3F) on a wireframe floor
//   - vignette + scanlines + grid overlay

// Lazy-load the 3D factory — it pulls in Three.js (~235KB gzipped) which
// is shared with WireframeCore so the second use is free. We render
// nothing as the fallback (other background layers are enough) to avoid
// any visual swap when the scene loads.
const RoboticFactory3D = lazy(() =>
  import("./RoboticFactory3D").then((m) => ({ default: m.RoboticFactory3D }))
);

export function Background() {
  return (
    <div className="bg-root" aria-hidden>
      <div className="bg-base" />
      <div className="bg-nebula nebula-a" />
      <div className="bg-nebula nebula-b" />
      <Suspense fallback={null}>
        <RoboticFactory3D />
      </Suspense>
      <div className="bg-grid" />
      <div className="bg-vignette" />
      <div className="bg-scanline" />
    </div>
  );
}
