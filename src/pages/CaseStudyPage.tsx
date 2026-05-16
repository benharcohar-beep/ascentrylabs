import { useEffect } from "react";
import { useParams, Link, Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowUpRight, ArrowRight } from "lucide-react";
import { PROJECTS, CATEGORIES, projectBySlug } from "../data/projects";
import { ConsultCta } from "./ConsultCta";
import "./case.css";

export function CaseStudyPage() {
  const { slug } = useParams<{ slug: string }>();
  const project = slug ? projectBySlug(slug) : undefined;

  useEffect(() => {
    if (!project) return;
    document.title = `${project.title} · Ascentry Labs`;
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [project]);

  if (!project) return <Navigate to="/portfolio" replace />;

  const cat = CATEGORIES.find((c) => c.id === project.cat);
  if (!cat) return <Navigate to="/portfolio" replace />;

  const related = PROJECTS.filter((p) => p.cat === project.cat && p.slug !== project.slug).slice(0, 3);

  return (
    <>
      <header className="case-head" style={{ ["--cat-color" as string]: cat.color }}>
        <div className="container">
          <Link to="/portfolio" className="case-back">
            <ArrowLeft size={14} />
            <span className="mono">ALL WORK</span>
          </Link>

          <div className="case-meta">
            <span className="mono case-code">{project.code}</span>
            <span className="case-cat-pill" style={{ color: cat.color, borderColor: cat.color }}>
              <span className="case-cat-dot" style={{ background: cat.color }} />
              {cat.label}
            </span>
          </div>

          <div className="mono case-client">{project.client}</div>
          <h1 className="case-title">{project.title}</h1>

          <div className="case-hero" aria-hidden>
            <svg viewBox="0 0 1000 320" preserveAspectRatio="xMidYMid slice">
              <defs>
                <pattern id={`case-pat-${project.code}`} width="48" height="48" patternUnits="userSpaceOnUse" patternTransform="rotate(20)">
                  <line x1="0" y1="0" x2="0" y2="48" stroke={cat.color} strokeWidth="0.6" opacity="0.32" />
                  <line x1="0" y1="0" x2="48" y2="0" stroke={cat.color} strokeWidth="0.6" opacity="0.18" />
                </pattern>
                <radialGradient id={`case-glow-${project.code}`} cx="50%" cy="50%" r="60%">
                  <stop offset="0%" stopColor={cat.color} stopOpacity="0.42" />
                  <stop offset="60%" stopColor={cat.color} stopOpacity="0.10" />
                  <stop offset="100%" stopColor={cat.color} stopOpacity="0" />
                </radialGradient>
              </defs>
              <rect width="1000" height="320" fill={`url(#case-pat-${project.code})`} />
              <rect width="1000" height="320" fill={`url(#case-glow-${project.code})`} />
              <text x="40" y="290" fontFamily="JetBrains Mono, monospace" fontSize="14" fill={cat.color} opacity="0.55" letterSpacing="3">
                [ {project.code}.JPG ]
              </text>
            </svg>
          </div>
        </div>
      </header>

      <section className="case-section">
        <div className="container case-grid">
          <aside className="case-side">
            <div className="case-side-block">
              <div className="mono dim">DOMAIN</div>
              <div className="case-side-v">{project.metrics[0]?.[1] ?? "—"}</div>
            </div>
            {project.metrics.slice(1).map(([k, v]) => (
              <div key={k} className="case-side-block">
                <div className="mono dim">{k.toUpperCase()}</div>
                <div className="case-side-v">{v}</div>
              </div>
            ))}
            <div className="case-side-block">
              <div className="mono dim">CODE</div>
              <div className="case-side-v mono">{project.code}</div>
            </div>
          </aside>

          <article className="case-body">
            <section className="case-block">
              <h2 className="case-h">Overview</h2>
              <p className="case-p">{project.desc}</p>
            </section>

            <section className="case-block">
              <h2 className="case-h">Outcomes</h2>
              <div className="case-outcomes">
                {project.metrics.map(([k, v], i) => (
                  <motion.div
                    key={k}
                    className="case-outcome"
                    style={{ ["--cat-color" as string]: cat.color }}
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-40px" }}
                    transition={{ duration: 0.5, delay: i * 0.08 }}
                  >
                    <div className="mono case-outcome-k">{k}</div>
                    <div className="case-outcome-v" style={{ color: cat.color }}>{v}</div>
                  </motion.div>
                ))}
              </div>
            </section>

            <section className="case-block">
              <h2 className="case-h">Stack</h2>
              <div className="case-tags">
                {project.tags.map((t) => (
                  <span key={t} className="case-tag">{t}</span>
                ))}
              </div>
            </section>

            <section className="case-block">
              <Link to="/#consult" className="btn btn-primary btn-fx">
                <span className="btn-bracket">[</span>
                Discuss a similar project
                <span className="btn-bracket">]</span>
                <ArrowUpRight size={14} />
              </Link>
            </section>
          </article>
        </div>
      </section>

      {related.length > 0 && (
        <section className="section case-related">
          <div className="container">
            <div className="case-related-head">
              <div className="eyebrow">More in {cat.label}</div>
              <Link to="/portfolio" className="case-related-all mono">
                ALL WORK <ArrowRight size={12} />
              </Link>
            </div>
            <div className="case-related-grid">
              {related.map((r) => {
                const rcat = CATEGORIES.find((c) => c.id === r.cat)!;
                return (
                  <Link
                    key={r.slug}
                    to={`/portfolio/${r.slug}`}
                    className="case-related-card glass"
                    style={{ ["--cat-color" as string]: rcat.color }}
                  >
                    <div className="case-related-card-top">
                      <span className="mono case-related-code">{r.code}</span>
                      <span className="mono case-related-cat" style={{ color: rcat.color }}>{rcat.label}</span>
                    </div>
                    <div className="case-related-client mono">{r.client}</div>
                    <h3 className="case-related-title">{r.title}</h3>
                    <span className="case-related-open mono">
                      OPEN <ArrowUpRight size={12} />
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        </section>
      )}

      <ConsultCta />
    </>
  );
}
