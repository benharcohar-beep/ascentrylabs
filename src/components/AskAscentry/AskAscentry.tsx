import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, X, Send, ArrowRight } from "lucide-react";
import { CONTACT_EMAIL } from "../../data/nav";
import "./ask.css";

type Msg = { role: "bot" | "user"; text: string; cta?: { label: string; href: string }[] };

// A small mock "AI" — pattern-matches against the user's question and
// returns a canned response in Ascentry's voice. Deliberately not wired
// to a real LLM — that requires API keys + cost. The point is to show
// what's possible and route real conversations to a human.
//
// For each keyword cluster we return a tight, opinionated answer plus a
// CTA pair that nudges the user toward booking a consultation.

type Reply = { text: string; cta?: { label: string; href: string }[] };

const QA: { match: RegExp; reply: Reply }[] = [
  {
    match: /(what (do|does)|who are you|tell me about|about ascentry|what is ascentry)/i,
    reply: {
      text:
        "Ascentry Labs is an AI & digital transformation consultancy. We do four things: assess where AI fits, design strategy, build the systems, and educate the people who'll use them. Founded by Hunter Sandidge — engineer behind life-support AI on the ISS and the next-gen NASA spacesuit copilot.",
      cta: [
        { label: "See services", href: "#services" },
        { label: "See work", href: "#portfolio" },
      ],
    },
  },
  {
    match: /(service|offer|engage|work with|hire)/i,
    reply: {
      text:
        "Six engagement types: AI Readiness Assessment (2–4w), Digital Strategy (4–10w), Advisory retainer (monthly), Custom Development (project-based), Executive AI Education (half/full day), and Keynote Speaking. Pick a starting point — we shape the engagement to fit.",
      cta: [
        { label: "Browse services", href: "#services" },
        { label: "Schedule a call", href: "#consult" },
      ],
    },
  },
  {
    match: /(cost|price|fee|budget|how much)/i,
    reply: {
      text:
        "Pricing depends on scope. Assessments start in the low-five-figures, retainers and full builds scale from there. The 30-min consultation is free and we'll tell you honestly whether we can help — even if the answer is no.",
      cta: [{ label: "Book free 30-min consult", href: "#consult" }],
    },
  },
  {
    match: /(hunter|founder|who built|who runs|who is)/i,
    reply: {
      text:
        "Hunter Sandidge: Founder & Principal. Built the ECLSS analytics platform on the ISS. Father of the AI copilot for the xEVAS spacesuit. Smart-factory and digital transformation lead at a Fortune 100. Top-rated applied-AI professor at Marquette/NMDSI.",
      cta: [{ label: "Read more", href: "#about" }],
    },
  },
  {
    match: /(case|portfolio|example|projects?|done)/i,
    reply: {
      text:
        "Fifteen shipped projects across modeling, agentic systems, digital transformation, and education. Highlights: NASA's Asteria spacesuit copilot, Leto life-support intelligence on the ISS, FactrEye smart-factory at Collins Aerospace, and an enterprise pricing platform that cut time-to-first-price by 60%.",
      cta: [{ label: "See the work", href: "#portfolio" }],
    },
  },
  {
    match: /(contact|email|reach|talk|call|book|consultation|consult|meet|speak)/i,
    reply: {
      text: `Easiest path: book the free 30-min consult. No deck, no pitch — just an honest conversation. Or email Hunter directly at ${CONTACT_EMAIL}.`,
      cta: [
        { label: "Schedule consult", href: "#consult" },
        { label: `Email ${CONTACT_EMAIL.split("@")[0]}`, href: `mailto:${CONTACT_EMAIL}` },
      ],
    },
  },
  {
    match: /(nasa|space|spacesuit|astronaut|iss)/i,
    reply: {
      text:
        "Yes — Ascentry has shipped real systems aboard the ISS (Leto, life-support analytics) and into NASA's xEVAS next-generation spacesuit program (Asteria copilot, adaptive thermal control). Aerospace and defense are where we cut our teeth.",
      cta: [{ label: "See space work", href: "#portfolio" }],
    },
  },
  {
    match: /(industry|sector|finance|defense|aerospace|manufacturing)/i,
    reply: {
      text:
        "Aerospace, defense, finance, manufacturing, and academia. Common thread: high-stakes environments where being wrong is expensive — so the AI has to be honest, traceable, and operationally useful, not flashy.",
    },
  },
  {
    match: /(team|hire me|jobs?|career)/i,
    reply: {
      text:
        "Ascentry is a small senior team that brings in specialists per engagement. We're not actively hiring junior roles, but if you've shipped serious applied-AI work and want to talk, email Hunter directly.",
      cta: [{ label: `Email ${CONTACT_EMAIL.split("@")[0]}`, href: `mailto:${CONTACT_EMAIL}` }],
    },
  },
  {
    match: /(start|begin|first step|get started)/i,
    reply: {
      text:
        "Start with the free 30-min consult. We'll talk through where you are, where you want to be, and whether AI is even the right answer. From there: typically a 2–4 week assessment to map opportunities and risks before any build.",
      cta: [{ label: "Book the consult", href: "#consult" }],
    },
  },
];

const FALLBACK: Reply = {
  text:
    "I'm a small on-page bot — for anything beyond the basics, the fastest path is a 30-min call with Hunter. He'll give you a real answer.",
  cta: [
    { label: "Book free consultation", href: "#consult" },
    { label: `Email ${CONTACT_EMAIL.split("@")[0]}`, href: `mailto:${CONTACT_EMAIL}` },
  ],
};

const QUICK_QUESTIONS = [
  "What does Ascentry do?",
  "Show me your work",
  "How much does it cost?",
  "Who is Hunter?",
];

const INITIAL_GREETING: Msg = {
  role: "bot",
  text: "Hi — I'm a small mock built into the site to give you the gist. Ask me anything about what Ascentry does.",
};

function answer(q: string): Reply {
  const found = QA.find((entry) => entry.match.test(q));
  return found?.reply ?? FALLBACK;
}

export function AskAscentry() {
  const [open, setOpen] = useState(false);
  const [hasNudged, setHasNudged] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([INITIAL_GREETING]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // After ~12s, gently pulse the launcher to draw the eye (once per session)
  useEffect(() => {
    if (open) return;
    let cancelled = false;
    try {
      if (sessionStorage.getItem("ascentry-ask-nudged")) return;
    } catch { /* ignore */ }
    const t = setTimeout(() => {
      if (!cancelled) {
        setHasNudged(true);
        try { sessionStorage.setItem("ascentry-ask-nudged", "1"); } catch { /* ignore */ }
      }
    }, 12000);
    return () => { cancelled = true; clearTimeout(t); };
  }, [open]);

  // Auto-scroll to bottom on new message
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking]);

  // Focus input when opened
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 220);
  }, [open]);

  // Esc closes + react to other dialogs opening
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    const onOther = (e: Event) => {
      const detail = (e as CustomEvent).detail as { source?: string } | undefined;
      if (detail?.source !== "ask-ascentry") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("ascentry:dialog-open", onOther);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("ascentry:dialog-open", onOther);
    };
  }, [open]);

  function send(question: string) {
    const q = question.trim();
    if (!q) return;
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setThinking(true);
    // Variable delay so it feels like it's actually composing, not instant
    const delay = 600 + Math.min(1400, q.length * 20);
    setTimeout(() => {
      const reply = answer(q);
      setMessages((m) => [...m, { role: "bot", text: reply.text, cta: reply.cta }]);
      setThinking(false);
    }, delay);
  }

  return (
    <>
      <button
        className={`ask-launcher ${open ? "is-open" : ""} ${hasNudged && !open ? "is-nudge" : ""}`}
        onClick={() => {
          setOpen((o) => {
            if (!o) {
              // Opening — close any other floating dialog
              window.dispatchEvent(new CustomEvent("ascentry:dialog-open", { detail: { source: "ask-ascentry" } }));
            }
            return !o;
          });
        }}
        aria-label={open ? "Close Ask Ascentry" : "Open Ask Ascentry"}
        title="Ask the on-page assistant (or just chat)"
      >
        {open ? <X size={18} /> : <Sparkles size={18} />}
        {!open && <span className="ask-launcher-label">Ask Ascentry</span>}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="ask-panel glass"
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.96 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            role="dialog"
            aria-label="Ask Ascentry assistant"
          >
            <header className="ask-head">
              <div className="ask-head-title">
                <span className="ask-status-dot" aria-hidden />
                <strong>Ascentry</strong>
                <span className="mono dim ask-head-meta">ASSISTANT · v0.1</span>
              </div>
              <button className="ask-close" onClick={() => setOpen(false)} aria-label="Close">
                <X size={16} />
              </button>
            </header>

            <div className="ask-scroll" ref={scrollRef}>
              {messages.map((m, i) => (
                <div key={i} className={`ask-msg ask-msg-${m.role}`}>
                  <div className="ask-msg-bubble">
                    <p>{m.text}</p>
                    {m.cta && (
                      <div className="ask-msg-cta">
                        {m.cta.map((c) => (
                          <a key={c.label} href={c.href} className="ask-cta-link" onClick={() => c.href.startsWith("#") && setOpen(false)}>
                            {c.label} <ArrowRight size={12} />
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {thinking && (
                <div className="ask-msg ask-msg-bot">
                  <div className="ask-msg-bubble">
                    <span className="ask-typing"><span /><span /><span /></span>
                  </div>
                </div>
              )}
            </div>

            {messages.length === 1 && (
              <div className="ask-quick">
                {QUICK_QUESTIONS.map((q) => (
                  <button key={q} className="ask-quick-chip" onClick={() => send(q)}>
                    {q}
                  </button>
                ))}
              </div>
            )}

            <form
              className="ask-form"
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
            >
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask anything…"
                spellCheck={false}
                autoComplete="off"
              />
              <button type="submit" className="ask-send" aria-label="Send" disabled={!input.trim() || thinking}>
                <Send size={14} />
              </button>
            </form>

            <footer className="ask-foot mono dim">
              On-page assistant · responses are demo
            </footer>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
