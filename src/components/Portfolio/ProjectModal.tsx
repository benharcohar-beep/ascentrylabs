import { useEffect, useState } from "react";
import { X, ArrowUpRight } from "lucide-react";
import type { Project, Category } from "../../data/projects";
import "./modal.css";

type Props = {
  project: Project | null;
  category: Category | null;
  onClose: () => void;
};

// Plain conditional render with a CSS transition for fade. Originally used
// framer-motion's AnimatePresence but ran into a React-19 quirk where the
// child wouldn't unmount on prop change — defaulting to vanilla React for
// reliability. Cheaper too.

export function ProjectModal({ project, category, onClose }: Props) {
  const [mounted, setMounted] = useState(false);

  // Mount when project arrives, unmount AFTER the exit transition has played.
  useEffect(() => {
    if (project) {
      setMounted(true);
    } else if (mounted) {
      // Hold the element for the duration of the exit fade
      const t = setTimeout(() => setMounted(false), 280);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project]);

  // Body-scroll lock + Esc to close + ping other dialogs to step aside
  useEffect(() => {
    if (!project) return;
    // Tell other floating dialogs (Ask Ascentry, Cmd+K) to close so the
    // modal owns the focus context.
    window.dispatchEvent(new CustomEvent("ascentry:dialog-open", { detail: { source: "portfolio-modal" } }));
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [project, onClose]);

  if (!mounted || !category) return null;

  // `is-open` drives the CSS fade-in. When `project` becomes null we drop
  // the class, which triggers fade-out before unmount.
  const open = !!project;

  return (
    <div className={`pmodal-root ${open ? "is-open" : "is-closing"}`}>
      <div className="pmodal-backdrop" onClick={onClose} />
      <div
        className="pmodal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pmodal-title"
        style={{ ["--cat-color" as string]: category.color }}
      >
        <div className="pmodal-corners" aria-hidden>
          <span /><span /><span /><span />
        </div>

        <button className="pmodal-close" onClick={onClose} aria-label="Close case study">
          <X size={20} />
        </button>

        <div className="pmodal-scroll">
          {project && (
            <>
              <header className="pmodal-head">
                <div className="pmodal-meta">
                  <span className="mono pmodal-code">{project.code}</span>
                  <span className="mono pmodal-cat" style={{ color: category.color }}>
                    <span className="pmodal-cat-dot" style={{ background: category.color }} />
                    {category.label}
                  </span>
                </div>
                <div className="pmodal-client mono">{project.client}</div>
                <h2 id="pmodal-title" className="pmodal-title">{project.title}</h2>
              </header>

              <div className="pmodal-hero" aria-hidden>
                <svg viewBox="0 0 800 240" preserveAspectRatio="xMidYMid slice">
                  <defs>
                    <pattern id={`pat-${project.code}`} width="42" height="42" patternUnits="userSpaceOnUse" patternTransform="rotate(20)">
                      <line x1="0" y1="0" x2="0" y2="42" stroke={category.color} strokeWidth="0.6" opacity="0.35" />
                      <line x1="0" y1="0" x2="42" y2="0" stroke={category.color} strokeWidth="0.6" opacity="0.18" />
                    </pattern>
                    <radialGradient id={`glow-${project.code}`} cx="50%" cy="50%" r="60%">
                      <stop offset="0%" stopColor={category.color} stopOpacity="0.45" />
                      <stop offset="60%" stopColor={category.color} stopOpacity="0.1" />
                      <stop offset="100%" stopColor={category.color} stopOpacity="0" />
                    </radialGradient>
                  </defs>
                  <rect width="800" height="240" fill={`url(#pat-${project.code})`} />
                  <rect width="800" height="240" fill={`url(#glow-${project.code})`} />
                  <text x="40" y="200" fontFamily="JetBrains Mono, monospace" fontSize="14" fill={category.color} opacity="0.55" letterSpacing="3">
                    [ {project.code}.JPG ]
                  </text>
                </svg>
              </div>

              <section className="pmodal-section">
                <h3 className="pmodal-section-h">Overview</h3>
                <p className="pmodal-body">{project.desc}</p>
              </section>

              <section className="pmodal-section">
                <h3 className="pmodal-section-h">Outcomes</h3>
                <div className="pmodal-metrics">
                  {project.metrics.map(([k, v]) => (
                    <div key={k} className="pmodal-metric">
                      <div className="mono pmodal-metric-k">{k}</div>
                      <div className="pmodal-metric-v">{v}</div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="pmodal-section">
                <h3 className="pmodal-section-h">Stack</h3>
                <div className="pmodal-tags">
                  {project.tags.map((t) => (
                    <span key={t} className="pmodal-tag">{t}</span>
                  ))}
                </div>
              </section>

              <footer className="pmodal-foot">
                <a href="#consult" className="btn btn-primary" onClick={onClose}>
                  Discuss a similar project
                  <ArrowUpRight size={14} />
                </a>
                <span className="mono dim">ESC TO CLOSE</span>
              </footer>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
