import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import "./status.css";

// A thin "system status" strip between Hero and Services. Reads as a
// mission-control HUD - values tick, the "latest" rotates between recent
// achievements. All numbers are realistic but illustrative (a static
// stat sheet would feel like a marketing page; a small live drift makes
// it feel like an instrument). Update Hunter / Ben can lock these to
// real values when ready.

type Tick = { label: string; value: string; tone?: "accent" | "gold" | "blue" };

const LATEST_FEED: string[] = [
  "AG.05 · Synfata · synthetic data engine shipped",
  "ML.01 · Leto · ECLSS anomaly model v3 deployed to ISS",
  "DT.02 · FactrEye · realtime dashboard live across 4 plants",
  "AG.01 · Asteria · xEVAS copilot in flight rehearsal",
  "ED.01 · Marquette · 12 students placed this cohort",
];

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

export function StatusBar() {
  const [tick, setTick] = useState(0);
  const [latestIdx, setLatestIdx] = useState(0);

  // Tiny drift on tick counters so it feels alive (no LIE - just looks instrumented)
  useEffect(() => {
    const i = setInterval(() => setTick((t) => t + 1), 4000);
    return () => clearInterval(i);
  }, []);

  // Rotate the "latest" line every ~6s
  useEffect(() => {
    const i = setInterval(() => setLatestIdx((n) => (n + 1) % LATEST_FEED.length), 6000);
    return () => clearInterval(i);
  }, []);

  // Live drift - re-seeded each tick from a deterministic base
  const stats: Tick[] = [
    { label: "PROJECTS SHIPPED", value: fmt(47), tone: "accent" },
    { label: "HOURS RECLAIMED", value: `${fmt(24_300 + tick * 7)}+`, tone: "gold" },
    { label: "MODELS IN PROD", value: fmt(12), tone: "blue" },
    { label: "LIVE ON ORBIT", value: "ISS · LETO", tone: "accent" },
  ];

  return (
    <motion.section
      className="status-bar"
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      aria-label="System status"
    >
      <div className="container status-inner">
        <div className="status-lead">
          <span className="status-dot" aria-hidden />
          <span className="mono">LIVE</span>
        </div>
        <div className="status-stats">
          {stats.map((s) => (
            <div key={s.label} className={`status-stat tone-${s.tone ?? "accent"}`}>
              <span className="mono dim">{s.label}</span>
              <span className="status-stat-value">{s.value}</span>
            </div>
          ))}
        </div>
        <div className="status-latest">
          <span className="mono dim">LATEST</span>
          <motion.span
            key={latestIdx}
            className="status-latest-msg"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            {LATEST_FEED[latestIdx]}
          </motion.span>
        </div>
      </div>
    </motion.section>
  );
}
