import { motion } from "framer-motion";
import { SERVICES } from "../../data/services";
import { TiltCard } from "../ui/TiltCard";
import { Check, Sparkles, ArrowUpRight, Compass, Map, Users, Code2, GraduationCap, Mic } from "lucide-react";
import "./services.css";

const ICONS = {
  compass: Compass,
  map: Map,
  users: Users,
  code: Code2,
  graduation: GraduationCap,
  mic: Mic,
} as const;

function openFinder() {
  window.dispatchEvent(new CustomEvent("ascentry:open-finder"));
}

export function Services() {
  return (
    <section className="section services" id="services">
      <div className="container">
        <div className="section-head">
          <div>
            <div className="eyebrow">02 — Services</div>
            <h2 className="section-title">Six ways we work together.</h2>
            <p className="section-sub">
              From a single readiness sprint to a long-term technical partner. Pick a starting point — we shape the engagement to fit.
            </p>
          </div>
          <div className="section-num">[ S.01 — S.06 ]</div>
        </div>

        <button className="finder-cta" onClick={openFinder} type="button">
          <span className="finder-cta-icon"><Sparkles size={16} /></span>
          <span className="finder-cta-body">
            <span className="mono finder-cta-eyebrow">FIND WHAT FITS · 4 QUESTIONS</span>
            <span className="finder-cta-label">Not sure which engagement to start with? Let me match you.</span>
          </span>
          <span className="finder-cta-arrow">
            <ArrowUpRight size={16} />
          </span>
          <span className="finder-cta-scan" aria-hidden />
        </button>

        <div className="services-grid">
          {SERVICES.map((s, i) => (
            <motion.div
              key={s.cat}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.7, delay: (i % 3) * 0.1, ease: [0.22, 1, 0.36, 1] }}
            >
              <TiltCard
                className="service-card glass float-card"
                intensity={4}
                style={{ ["--card-accent" as string]: s.color }}
              >
                <header className="service-head">
                  <span className="mono service-cat">{s.cat}</span>
                  <span className="mono service-num">{String(i + 1).padStart(2, "0")}</span>
                </header>
                <div className="service-icon" aria-hidden>
                  {(() => {
                    const Icon = ICONS[s.icon];
                    return <Icon size={48} strokeWidth={1.2} />;
                  })()}
                </div>
                <h3 className="service-title">{s.title}</h3>
                <p className="service-desc">{s.desc}</p>
                <ul className="service-bullets">
                  {s.bullets.map((b) => (
                    <li key={b}>
                      <Check size={14} className="bullet-check" />
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
                <footer className="service-foot">
                  <span className="mono dim">DURATION</span>
                  <span className="service-duration">{s.duration}</span>
                </footer>
                <div className="service-corner-tl" aria-hidden />
                <div className="service-corner-br" aria-hidden />
              </TiltCard>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
