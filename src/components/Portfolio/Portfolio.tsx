import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { CATEGORIES, PROJECTS } from "../../data/projects";
import { TiltCard } from "../ui/TiltCard";
import { ArrowUpRight } from "lucide-react";
import "./portfolio.css";

export function Portfolio() {
  const [activeCat, setActiveCat] = useState<string>("all");

  const filtered = useMemo(() => {
    if (activeCat === "all") return PROJECTS;
    return PROJECTS.filter((p) => p.cat === activeCat);
  }, [activeCat]);

  return (
    <section className="section portfolio" id="portfolio">
      <div className="container">
        <div className="section-head">
          <div>
            <div className="eyebrow">03 - Portfolio</div>
            <h2 className="section-title">Selected work.</h2>
            <p className="section-sub">
              Spanning modeling, agentic systems, digital transformation, and education. Each project shipped under real conditions with real consequences. Click any card for the full case study.
            </p>
          </div>
          <div className="section-num">[ {String(filtered.length).padStart(2, "0")} / {String(PROJECTS.length).padStart(2, "0")} ]</div>
        </div>

        <div className="port-tabs">
          <button
            className={`port-tab ${activeCat === "all" ? "is-active" : ""}`}
            onClick={() => setActiveCat("all")}
            style={activeCat === "all" ? { color: "var(--accent)", borderColor: "var(--accent)" } : {}}
          >
            <span className="port-tab-dot" style={{ background: "var(--accent)" }} />
            <span>All</span>
            <span className="mono dim">{PROJECTS.length}</span>
          </button>
          {CATEGORIES.map((c) => {
            const isActive = c.id === activeCat;
            const count = PROJECTS.filter((p) => p.cat === c.id).length;
            return (
              <button
                key={c.id}
                className={`port-tab ${isActive ? "is-active" : ""}`}
                onClick={() => setActiveCat(c.id)}
                style={isActive ? { color: c.color, borderColor: c.color } : {}}
              >
                <span className="port-tab-dot" style={{ background: c.color }} />
                <span>{c.label}</span>
                <span className="mono dim">{count}</span>
              </button>
            );
          })}
        </div>

        <motion.div className="port-grid" layout>
          <AnimatePresence mode="popLayout">
            {filtered.map((p, i) => {
              const cat = CATEGORIES.find((c) => c.id === p.cat)!;
              return (
                <motion.div
                  key={p.code}
                  layout
                  initial={{ opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -16, transition: { duration: 0.2 } }}
                  transition={{ duration: 0.55, delay: (i % 6) * 0.06, ease: [0.22, 1, 0.36, 1] }}
                >
                  <TiltCard
                    className={`port-card glass ${p.featured ? "is-featured" : ""}`}
                    intensity={3}
                    style={{ ["--cat-color" as string]: cat.color }}
                  >
                    <Link
                      to={`/portfolio/${p.slug}`}
                      className="port-card-button"
                      aria-label={`Open case study: ${p.title}`}
                    >
                      <div className="port-card-top">
                        <span className="mono port-card-code">{p.code}</span>
                        <span className="mono port-card-cat" style={{ color: cat.color }}>{cat.label}</span>
                      </div>
                      <div className="port-card-client mono">{p.client}</div>
                      <h3 className="port-card-title">{p.title}</h3>
                      <p className="port-card-desc">{p.desc}</p>
                      <div className="port-card-metrics">
                        {p.metrics.map(([k, v]) => (
                          <div key={k} className="port-metric">
                            <span className="mono dim">{k}</span>
                            <span>{v}</span>
                          </div>
                        ))}
                      </div>
                      <div className="port-card-bottom">
                        <div className="port-card-tags">
                          {p.tags.map((t) => (
                            <span key={t} className="port-tag">{t}</span>
                          ))}
                        </div>
                        <span className="port-card-open mono">
                          OPEN <ArrowUpRight size={12} />
                        </span>
                      </div>
                    </Link>
                  </TiltCard>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </motion.div>
      </div>
    </section>
  );
}
