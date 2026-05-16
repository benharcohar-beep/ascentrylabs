import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import "./page-transition.css";

// Mission-control scan-line transition. Fires on every route change:
// a bright cyan bar sweeps top→bottom across the viewport (~600ms),
// a brief "TRANSMITTING" readout flickers in the corner, and corner
// brackets pulse in. The actual page swap happens beneath the overlay,
// so users see the new page revealed by the sweep rather than a flash
// of blank space.
//
// Respects prefers-reduced-motion (skips the animation entirely).

export function PageTransition() {
  const location = useLocation();
  const [activeKey, setActiveKey] = useState(0);
  const [enabled] = useState(() =>
    typeof window !== "undefined" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    if (!enabled) return;
    // Toggle the key so the CSS keyframe restarts on every navigation
    setActiveKey((k) => k + 1);
  }, [location.pathname, enabled]);

  if (!enabled) return null;

  return (
    <div
      key={activeKey}
      className="pt-overlay"
      aria-hidden
    >
      {/* The sweeping scan bar */}
      <div className="pt-scan" />
      {/* Trailing dim glow that follows the scan */}
      <div className="pt-scan-trail" />
      {/* Corner brackets that flash in at the start */}
      <span className="pt-corner pt-tl" />
      <span className="pt-corner pt-tr" />
      <span className="pt-corner pt-bl" />
      <span className="pt-corner pt-br" />
      {/* Transmitting label */}
      <div className="pt-label mono">
        <span className="pt-label-dot" />
        TRANSMITTING
      </div>
    </div>
  );
}
