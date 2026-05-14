import { useEffect, useRef, useState } from "react";
import "./factory.css";

// Wireframe industrial robotic arms in the background — they pick, rotate,
// place, and return on a slow continuous cycle. Each arm has its own size,
// position, and phase offset so the floor reads as a busy factory rather
// than a row of synchronized clones. Plus a subtle horizontal conveyor
// belt with travelling parts and occasional spark bursts at the grippers.
//
// Pure SVG + CSS — sharp at any zoom, light on the GPU. Animations driven
// by CSS keyframes so they keep working when the tab is backgrounded
// (rAF-throttled) and so prefers-reduced-motion can pause everything via
// a single rule.

type Arm = {
  id: string;
  x: number;          // % from left
  y: number;          // % from top (where the BASE sits)
  scale: number;      // overall scale
  flip: boolean;      // mirror left/right
  delay: number;      // animation phase (s)
  hue: "cyan" | "blue" | "gold";
  cycle: number;      // animation cycle length (s)
};

const ARMS: Arm[] = [
  { id: "a1", x: 8,  y: 78, scale: 1.4,  flip: false, delay: 0,    hue: "cyan", cycle: 9 },
  { id: "a2", x: 28, y: 92, scale: 1.0,  flip: true,  delay: -2.2, hue: "blue", cycle: 8 },
  { id: "a3", x: 48, y: 82, scale: 0.85, flip: false, delay: -4.5, hue: "cyan", cycle: 11 },
  { id: "a4", x: 72, y: 88, scale: 1.15, flip: true,  delay: -1.1, hue: "gold", cycle: 9 },
  { id: "a5", x: 92, y: 76, scale: 1.0,  flip: false, delay: -6.0, hue: "cyan", cycle: 10 },
];

const SPARK_INTERVAL_MS = 2200;

type Spark = { id: number; x: number; y: number; hue: string };

export function RoboticFactory() {
  const [sparks, setSparks] = useState<Spark[]>([]);
  const sparkCounter = useRef(0);
  const armRefs = useRef<Record<string, SVGSVGElement | null>>({});

  // Periodically emit a spark at one of the arms' grippers — visualizes
  // the "completed" moment of a pick/place cycle.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const interval = setInterval(() => {
      const arm = ARMS[Math.floor(Math.random() * ARMS.length)];
      const el = armRefs.current[arm.id];
      if (!el) return;
      const rect = el.getBoundingClientRect();
      // Spark at upper-right (or upper-left if flipped) — roughly where the gripper ends up
      const sx = arm.flip ? rect.left + rect.width * 0.25 : rect.left + rect.width * 0.75;
      const sy = rect.top + rect.height * 0.18;
      const id = ++sparkCounter.current;
      const hueMap = { cyan: "127, 209, 211", blue: "91, 157, 217", gold: "255, 192, 0" };
      setSparks((prev) => [...prev.slice(-6), { id, x: sx, y: sy, hue: hueMap[arm.hue] }]);
      setTimeout(() => {
        setSparks((prev) => prev.filter((s) => s.id !== id));
      }, 900);
    }, SPARK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="factory" aria-hidden>
      {/* Conveyor strip near the bottom — horizontal "belt" with travelling crates */}
      <div className="conveyor">
        <div className="conveyor-belt" />
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="conveyor-part" style={{ animationDelay: `${-i * 5}s` }} />
        ))}
      </div>

      {/* The arms */}
      <div className="factory-arms">
        {ARMS.map((arm) => (
          <Arm key={arm.id} arm={arm} svgRef={(el) => { armRefs.current[arm.id] = el; }} />
        ))}
      </div>

      {/* Sparks layer — rendered above arms */}
      <div className="factory-sparks">
        {sparks.map((s) => (
          <span
            key={s.id}
            className="factory-spark"
            style={{
              left: s.x,
              top: s.y,
              ["--spark-color" as string]: `rgba(${s.hue}, 1)`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

function Arm({ arm, svgRef }: { arm: Arm; svgRef: (el: SVGSVGElement | null) => void }) {
  const hueColor = arm.hue === "cyan" ? "#7fd1d3" : arm.hue === "blue" ? "#5b9dd9" : "#ffc000";
  // ViewBox is fixed; CSS handles scaling.
  return (
    <svg
      ref={svgRef}
      className={`arm arm-hue-${arm.hue} ${arm.flip ? "arm-flip" : ""}`}
      viewBox="0 0 200 320"
      style={{
        left: `${arm.x}%`,
        top: `${arm.y}%`,
        transform: `translate(-50%, -100%) scale(${arm.scale}) ${arm.flip ? "scaleX(-1)" : ""}`,
        ["--arm-cycle" as string]: `${arm.cycle}s`,
        ["--arm-delay" as string]: `${arm.delay}s`,
        color: hueColor,
      }}
    >
      <defs>
        <linearGradient id={`grad-${arm.id}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={hueColor} stopOpacity="0.25" />
          <stop offset="100%" stopColor={hueColor} stopOpacity="0.55" />
        </linearGradient>
      </defs>

      {/* Floor plate */}
      <g className="arm-base">
        <path d="M 60 318 L 80 290 L 120 290 L 140 318 Z" fill="rgba(127,209,211,0.05)" stroke={hueColor} strokeWidth="0.8" strokeOpacity="0.55" />
        <line x1="60" y1="318" x2="140" y2="318" stroke={hueColor} strokeWidth="1.2" strokeOpacity="0.8" />
        {/* Mount studs */}
        <circle cx="72" cy="312" r="1.2" fill={hueColor} fillOpacity="0.7" />
        <circle cx="128" cy="312" r="1.2" fill={hueColor} fillOpacity="0.7" />
      </g>

      {/* Shoulder pivot — anchors the entire articulated upper arm.
          We rotate this whole group around its origin (100, 290). */}
      <g className="arm-shoulder" style={{ transformOrigin: "100px 290px" }}>
        {/* Shoulder hub */}
        <circle cx="100" cy="290" r="9" fill="rgba(0,0,0,0.6)" stroke={hueColor} strokeWidth="0.9" strokeOpacity="0.85" />
        <circle cx="100" cy="290" r="4" fill={hueColor} fillOpacity="0.5" />
        <circle cx="100" cy="290" r="1.4" fill={hueColor} fillOpacity="1" />

        {/* Upper arm — bar from shoulder to elbow */}
        <path
          d="M 92 290 L 92 180 L 108 180 L 108 290 Z"
          fill={`url(#grad-${arm.id})`}
          fillOpacity="0.18"
          stroke={hueColor}
          strokeWidth="0.9"
          strokeOpacity="0.85"
        />
        {/* Internal tension lines */}
        <line x1="92" y1="220" x2="108" y2="220" stroke={hueColor} strokeWidth="0.4" strokeOpacity="0.4" />
        <line x1="92" y1="250" x2="108" y2="250" stroke={hueColor} strokeWidth="0.4" strokeOpacity="0.4" />

        {/* Elbow pivot */}
        <g className="arm-elbow" style={{ transformOrigin: "100px 180px" }}>
          {/* Elbow hub */}
          <circle cx="100" cy="180" r="7.5" fill="rgba(0,0,0,0.6)" stroke={hueColor} strokeWidth="0.9" strokeOpacity="0.85" />
          <circle cx="100" cy="180" r="3" fill={hueColor} fillOpacity="0.55" />

          {/* Forearm */}
          <path
            d="M 94 180 L 94 90 L 106 90 L 106 180 Z"
            fill={`url(#grad-${arm.id})`}
            fillOpacity="0.18"
            stroke={hueColor}
            strokeWidth="0.85"
            strokeOpacity="0.85"
          />
          <line x1="94" y1="120" x2="106" y2="120" stroke={hueColor} strokeWidth="0.4" strokeOpacity="0.35" />

          {/* Wrist pivot */}
          <g className="arm-wrist" style={{ transformOrigin: "100px 90px" }}>
            <circle cx="100" cy="90" r="6" fill="rgba(0,0,0,0.6)" stroke={hueColor} strokeWidth="0.85" strokeOpacity="0.85" />
            <circle cx="100" cy="90" r="2.5" fill={hueColor} fillOpacity="0.55" />

            {/* Gripper assembly — shaft + two-pronged claw */}
            <g className="arm-gripper">
              <line x1="100" y1="90" x2="100" y2="55" stroke={hueColor} strokeWidth="1" strokeOpacity="0.9" />
              {/* Claw fingers — these open/close via class .arm-gripper-open */}
              <g className="arm-gripper-finger arm-gripper-l" style={{ transformOrigin: "100px 55px" }}>
                <path d="M 100 55 L 92 38 L 92 28 L 96 28 L 96 36 L 102 52 Z" fill={`url(#grad-${arm.id})`} fillOpacity="0.25" stroke={hueColor} strokeWidth="0.85" strokeOpacity="0.9" />
              </g>
              <g className="arm-gripper-finger arm-gripper-r" style={{ transformOrigin: "100px 55px" }}>
                <path d="M 100 55 L 108 38 L 108 28 L 104 28 L 104 36 L 98 52 Z" fill={`url(#grad-${arm.id})`} fillOpacity="0.25" stroke={hueColor} strokeWidth="0.85" strokeOpacity="0.9" />
              </g>
              {/* Wrist tag — tiny code */}
              <text x="115" y="52" fontFamily="JetBrains Mono, monospace" fontSize="6" fill={hueColor} fillOpacity="0.5">{arm.id.toUpperCase()}</text>
            </g>
          </g>
        </g>
      </g>

      {/* Power cable trailing from the side */}
      <path d="M 60 310 Q 30 305 25 300 Q 20 290 30 290" stroke={hueColor} strokeWidth="0.6" strokeOpacity="0.35" fill="none" />
    </svg>
  );
}
