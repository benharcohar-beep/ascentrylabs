import { motion } from "framer-motion";
import { TiltCard } from "../ui/TiltCard";
import "./about.css";

const HIGHLIGHTS = [
  { num: "15+", label: "Years in industry", color: "var(--accent)" },
  { num: "$10B+", label: "Portfolios touched", color: "var(--gold)" },
  { num: "170+", label: "Processes automated", color: "var(--blue)" },
  { num: "ISS", label: "Live in orbit", color: "var(--violet)" },
];

const RESUME = [
  {
    period: "Now",
    role: "Founder & Principal",
    org: "Ascentry Labs",
    note: "Strategy, applied AI, and digital transformation for enterprises that can't afford ambiguity.",
  },
  {
    period: "Recent",
    role: "Lead Engineer · Asteria & Leto",
    org: "NASA · ISS / xEVAS",
    note: "AI copilot for next-generation spacesuits. Predictive analytics for life support aboard the International Space Station.",
  },
  {
    period: "Earlier",
    role: "Smart Factory & Digital Transformation Lead",
    org: "Fortune 100 Aerospace",
    note: "Built the data platform and automation suite that 170+ business processes now run on. Multi-billion-dollar portfolio.",
  },
  {
    period: "Always",
    role: "Lecturer · Applied AI & FinTech",
    org: "Marquette University · NMDSI",
    note: "Top-rated professor for connecting AI to real business decisions. Translating advanced technique into useful judgment.",
  },
];

export function About() {
  return (
    <section className="section about" id="about">
      <div className="container">
        <div className="section-head">
          <div>
            <div className="eyebrow">04 — About</div>
            <h2 className="section-title">A part of the AI landscape<br />most people never see.</h2>
            <p className="section-sub">
              Ascentry Labs is led by Hunter Sandidge — a builder who has spent his career operating where the
              stakes are highest: spacesuits, factories, and balance sheets. We bring that same discipline to
              every engagement.
            </p>
          </div>
          <div className="section-num">[ A.01 ]</div>
        </div>

        <div className="about-grid">
          {HIGHLIGHTS.map((h, i) => (
            <motion.div
              key={h.label}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] }}
            >
              <TiltCard className="about-stat glass" intensity={5}>
                <div className="about-stat-num" style={{ color: h.color, textShadow: `0 0 24px ${h.color}` }}>
                  {h.num}
                </div>
                <div className="about-stat-label">{h.label}</div>
              </TiltCard>
            </motion.div>
          ))}
        </div>

        <div className="about-resume">
          <div className="about-resume-line" aria-hidden />
          {RESUME.map((r, i) => (
            <motion.div
              key={r.role}
              className="about-resume-item"
              initial={{ opacity: 0, x: -16 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
            >
              <div className="about-resume-marker" aria-hidden />
              <div className="about-resume-period mono">{r.period}</div>
              <div className="about-resume-body">
                <h3 className="about-resume-role">{r.role}</h3>
                <div className="about-resume-org mono">{r.org}</div>
                <p className="about-resume-note">{r.note}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
