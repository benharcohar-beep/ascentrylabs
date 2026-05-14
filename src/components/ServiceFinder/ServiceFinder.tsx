import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowUpRight, Sparkles, X, RotateCw, Check } from "lucide-react";
import { SERVICES } from "../../data/services";
import "./finder.css";

// 4-question wizard that scores each answer against the 6 service
// categories and recommends the best fit. Each option carries a
// `weights` object: { ASSESSMENT: 3, STRATEGY: 1, ... }. The cat with
// the highest tallied score wins; the next two are shown as
// alternatives.

type ServiceCat = "ASSESSMENT" | "STRATEGY" | "ADVISORY" | "BUILD" | "EDUCATION" | "SPEAKING";

type Option = {
  id: string;
  label: string;
  hint?: string;
  weights: Partial<Record<ServiceCat, number>>;
};

type Question = {
  id: string;
  prompt: string;
  sub?: string;
  options: Option[];
};

const QUESTIONS: Question[] = [
  {
    id: "stage",
    prompt: "Where are you in your AI journey?",
    sub: "Pick the closest description. We'll narrow down from here.",
    options: [
      { id: "curious", label: "Curious — exploring what AI could do for us", weights: { ASSESSMENT: 3, EDUCATION: 1 } },
      { id: "ideas", label: "We have specific use cases in mind, but no plan yet", weights: { STRATEGY: 3, ASSESSMENT: 1 } },
      { id: "plan", label: "We have a plan and need help executing it", weights: { ADVISORY: 3, BUILD: 2 } },
      { id: "tool", label: "We need a custom tool built that doesn't exist off the shelf", weights: { BUILD: 3, STRATEGY: 1 } },
      { id: "upskill", label: "We need to upskill our team or leadership on AI", weights: { EDUCATION: 3 } },
      { id: "speaker", label: "We need a speaker for an event", weights: { SPEAKING: 4 } },
    ],
  },
  {
    id: "outcome",
    prompt: "What does success look like in six months?",
    options: [
      { id: "roadmap", label: "A clear, prioritized roadmap of what to build", weights: { ASSESSMENT: 2, STRATEGY: 2 } },
      { id: "systems", label: "Real systems running in production", weights: { BUILD: 3, ADVISORY: 1 } },
      { id: "team", label: "Our team is confident with AI tools and concepts", weights: { EDUCATION: 3, ADVISORY: 1 } },
      { id: "leadership", label: "Leadership is aligned on an AI strategy", weights: { STRATEGY: 2, EDUCATION: 2 } },
      { id: "event", label: "We delivered a great event with a memorable keynote", weights: { SPEAKING: 4 } },
    ],
  },
  {
    id: "who",
    prompt: "Who's mostly involved?",
    options: [
      { id: "solo", label: "Just me / a small leadership group", weights: { EDUCATION: 1, ADVISORY: 1, ASSESSMENT: 1 } },
      { id: "leads", label: "Leadership plus a few key contributors", weights: { STRATEGY: 2, ADVISORY: 1 } },
      { id: "xfn", label: "A cross-functional team across multiple departments", weights: { STRATEGY: 1, BUILD: 2 } },
      { id: "org", label: "The whole org / enterprise-wide initiative", weights: { STRATEGY: 2, ADVISORY: 2 } },
      { id: "external", label: "An external / conference audience", weights: { SPEAKING: 4 } },
    ],
  },
  {
    id: "time",
    prompt: "How much time can you commit?",
    options: [
      { id: "oneoff", label: "One-off engagement (a day or two)", weights: { SPEAKING: 2, EDUCATION: 2, ASSESSMENT: 1 } },
      { id: "weeks", label: "A few focused weeks", weights: { ASSESSMENT: 3, EDUCATION: 1 } },
      { id: "months", label: "One to three months", weights: { STRATEGY: 3, BUILD: 1 } },
      { id: "ongoing", label: "Ongoing — we'd value a long-term partner", weights: { ADVISORY: 3, BUILD: 2 } },
    ],
  },
];

type Props = { open: boolean; onClose: () => void };

export function ServiceFinder({ open, onClose }: Props) {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<(string | null)[]>([null, null, null, null]);
  const [mounted, setMounted] = useState(false);

  // Mount on open, hold for exit transition on close
  useEffect(() => {
    if (open) {
      setMounted(true);
    } else if (mounted) {
      const t = setTimeout(() => {
        setMounted(false);
        // Reset for next time
        setStep(0);
        setAnswers([null, null, null, null]);
      }, 300);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Body scroll lock + Esc + announce so other dialogs step aside
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.dispatchEvent(new CustomEvent("ascentry:dialog-open", { detail: { source: "service-finder" } }));
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  const totalSteps = QUESTIONS.length;
  const isResults = step === totalSteps;
  const allAnswered = answers.every(Boolean);

  // Score and rank services based on selected answers
  const ranked = useMemo(() => {
    if (!allAnswered) return [];
    const scores: Record<ServiceCat, number> = {
      ASSESSMENT: 0, STRATEGY: 0, ADVISORY: 0, BUILD: 0, EDUCATION: 0, SPEAKING: 0,
    };
    QUESTIONS.forEach((q, qi) => {
      const ansId = answers[qi];
      const opt = q.options.find((o) => o.id === ansId);
      if (!opt) return;
      Object.entries(opt.weights).forEach(([cat, w]) => {
        scores[cat as ServiceCat] += w as number;
      });
    });
    return SERVICES
      .map((s) => ({ service: s, score: scores[s.cat as ServiceCat] || 0 }))
      .sort((a, b) => b.score - a.score);
  }, [answers, allAnswered]);

  function pickAnswer(id: string) {
    const next = [...answers];
    next[step] = id;
    setAnswers(next);
    // Auto-advance after a brief pause for visual confirmation
    setTimeout(() => setStep((s) => Math.min(totalSteps, s + 1)), 280);
  }

  function reset() {
    setAnswers([null, null, null, null]);
    setStep(0);
  }

  if (!mounted) return null;

  const q = QUESTIONS[step];
  const top = ranked[0]?.service;
  const alts = ranked.slice(1, 3).map((r) => r.service);

  return (
    <div className={`finder-root ${open ? "is-open" : "is-closing"}`}>
      <div className="finder-backdrop" onClick={onClose} />
      <div className="finder" role="dialog" aria-modal="true" aria-labelledby="finder-title">
        <div className="finder-corners" aria-hidden>
          <span /><span /><span /><span />
        </div>

        <button className="finder-close" onClick={onClose} aria-label="Close">
          <X size={20} />
        </button>

        <header className="finder-head">
          <div className="mono finder-eyebrow">
            <Sparkles size={12} />
            FIND WHAT FITS
          </div>
          <div className="finder-progress" aria-hidden>
            {QUESTIONS.map((_, i) => (
              <span
                key={i}
                className={`finder-pip ${i < step || isResults ? "is-done" : ""} ${i === step ? "is-current" : ""}`}
              />
            ))}
          </div>
          {!isResults && (
            <div className="mono dim finder-step-label">
              QUESTION {String(step + 1).padStart(2, "0")} / {String(totalSteps).padStart(2, "0")}
            </div>
          )}
        </header>

        <div className="finder-scroll">
          {!isResults && (
            <div className="finder-question">
              <h2 id="finder-title" className="finder-prompt">{q.prompt}</h2>
              {q.sub && <p className="finder-sub">{q.sub}</p>}
              <div className="finder-options">
                {q.options.map((o) => {
                  const isSelected = answers[step] === o.id;
                  return (
                    <button
                      key={o.id}
                      className={`finder-option ${isSelected ? "is-selected" : ""}`}
                      onClick={() => pickAnswer(o.id)}
                    >
                      <span className="finder-option-marker" aria-hidden>
                        <Check size={12} />
                      </span>
                      <span className="finder-option-label">{o.label}</span>
                      {o.hint && <span className="finder-option-hint dim">{o.hint}</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {isResults && top && (
            <div className="finder-results">
              <div className="finder-result-eyebrow mono">
                <span className="finder-dot" style={{ background: top.color }} />
                BEST FIT · {top.cat}
              </div>
              <h2 id="finder-title" className="finder-result-title">{top.title}</h2>
              <p className="finder-result-desc">{top.desc}</p>

              <div className="finder-result-meta">
                {top.bullets.map((b) => (
                  <div key={b} className="finder-result-bullet">
                    <span className="finder-bullet-dot" style={{ background: top.color }} />
                    {b}
                  </div>
                ))}
              </div>

              <div className="finder-result-stats">
                <div className="finder-stat">
                  <div className="mono dim">DURATION</div>
                  <div className="finder-stat-v">{top.duration}</div>
                </div>
                <div className="finder-stat">
                  <div className="mono dim">CATEGORY</div>
                  <div className="finder-stat-v" style={{ color: top.color }}>{top.cat}</div>
                </div>
              </div>

              {alts.length > 0 && (
                <div className="finder-alts">
                  <div className="mono dim finder-alts-h">ALSO CONSIDER</div>
                  <div className="finder-alts-grid">
                    {alts.map((a) => (
                      <div key={a.cat} className="finder-alt" style={{ ["--alt-color" as string]: a.color }}>
                        <div className="mono finder-alt-cat" style={{ color: a.color }}>{a.cat}</div>
                        <div className="finder-alt-title">{a.title}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <footer className="finder-result-foot">
                <a
                  href="#consult"
                  className="btn btn-primary btn-fx"
                  onClick={onClose}
                >
                  <span className="btn-bracket">[</span>
                  Schedule a consultation about this
                  <span className="btn-bracket">]</span>
                  <ArrowUpRight size={14} />
                </a>
                <button className="finder-reset" onClick={reset}>
                  <RotateCw size={14} />
                  Start over
                </button>
              </footer>
            </div>
          )}
        </div>

        {!isResults && (
          <footer className="finder-foot">
            <button
              className="finder-back"
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              disabled={step === 0}
            >
              <ArrowLeft size={14} />
              Back
            </button>
            <span className="mono dim">ESC TO CLOSE</span>
          </footer>
        )}
      </div>
    </div>
  );
}
