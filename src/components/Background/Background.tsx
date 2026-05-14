import { RoboticFactory } from "./RoboticFactory";
import "./background.css";

// Composition for the "AI factory" mood (clean, mission-control):
//   - dim base gradient
//   - two faint nebula gradients (kept for ambient depth, very low opacity)
//   - articulated wireframe robotic arms working a conveyor belt
//   - vignette + scanlines + grid overlay (reads as factory floor + walls)
export function Background() {
  return (
    <div className="bg-root" aria-hidden>
      <div className="bg-base" />
      <div className="bg-nebula nebula-a" />
      <div className="bg-nebula nebula-b" />
      <RoboticFactory />
      <div className="bg-grid" />
      <div className="bg-vignette" />
      <div className="bg-scanline" />
    </div>
  );
}
