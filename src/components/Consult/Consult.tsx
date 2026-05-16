import { useState } from "react";
import { motion } from "framer-motion";
import { CONTACT_EMAIL } from "../../data/nav";
import { Mail, Send, ShieldCheck, Sparkles, ArrowUpRight, Calendar, MessageSquare } from "lucide-react";
import { CalendlyEmbed } from "./CalendlyEmbed";
import "./consult.css";

// Hunter's Calendly URL — placeholder. Swap this for his real one and
// the booking widget below becomes the live conversion path.
const CALENDLY_URL = "https://calendly.com/hunter-ascentrylabs/30min";

type FormState = { name: string; email: string; company: string; message: string };
type Tab = "book" | "message";

export function Consult() {
  const [tab, setTab] = useState<Tab>("book");
  const [form, setForm] = useState<FormState>({ name: "", email: "", company: "", message: "" });
  const [submitted, setSubmitted] = useState(false);

  const onChange = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setForm({ ...form, [k]: e.target.value });
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Placeholder behavior — open the user's mail client with a prefilled draft.
    // Replace with Web3Forms / Formspree / your endpoint when ready.
    const subject = encodeURIComponent(`Consultation request from ${form.name || "Website"}`);
    const body = encodeURIComponent(
      `Name: ${form.name}\nEmail: ${form.email}\nCompany: ${form.company}\n\n${form.message}`
    );
    window.location.href = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;
    setSubmitted(true);
  };

  return (
    <section className="section consult" id="consult">
      <div className="container">
        <div className="consult-grid">
          <motion.div
            className="consult-left"
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6 }}
          >
            <div className="eyebrow">06 — Consult</div>
            <h2 className="section-title">
              Ready to bring your<br />company into the era of <span className="hero-accent">AI?</span>
            </h2>
            <p className="consult-lead">
              Schedule a free 30-minute consultation. No slide deck, no pitch — just an honest conversation about
              where you are and what's next.
            </p>

            <ul className="consult-trust">
              <li>
                <ShieldCheck size={16} className="consult-trust-icon" />
                <div>
                  <strong>Completely free</strong>
                  <span className="dim mono">NEVER SHARED</span>
                </div>
              </li>
              <li>
                <Sparkles size={16} className="consult-trust-icon" />
                <div>
                  <strong>Honest assessment</strong>
                  <span className="dim mono">— EVEN IF "NO" IS THE ANSWER</span>
                </div>
              </li>
              <li>
                <Mail size={16} className="consult-trust-icon" />
                <div>
                  <strong>NDA available on request</strong>
                  <span className="dim mono">DISCRETION BY DEFAULT</span>
                </div>
              </li>
            </ul>

            <a href={`mailto:${CONTACT_EMAIL}`} className="consult-direct">
              <span className="mono dim">OR EMAIL DIRECTLY</span>
              <span className="consult-direct-email">
                {CONTACT_EMAIL}
                <ArrowUpRight size={14} />
              </span>
            </a>
          </motion.div>

          <motion.div
            className="consult-right"
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            <div className="glass consult-card">
              <div className="consult-card-corners" aria-hidden>
                <span /><span /><span /><span />
              </div>

              {/* Tab switcher: Book a time (Calendly) vs Send a message (form) */}
              <div className="consult-tabs" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "book"}
                  className={`consult-tab ${tab === "book" ? "is-active" : ""}`}
                  onClick={() => setTab("book")}
                >
                  <Calendar size={14} />
                  Book a time
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "message"}
                  className={`consult-tab ${tab === "message" ? "is-active" : ""}`}
                  onClick={() => { setTab("message"); setSubmitted(false); }}
                >
                  <MessageSquare size={14} />
                  Send a message
                </button>
              </div>

              {tab === "book" && (
                <div className="consult-book">
                  <div className="consult-book-meta mono dim">
                    PICK A 30-MIN SLOT · NO PREP NEEDED
                  </div>
                  <CalendlyEmbed url={CALENDLY_URL} />
                </div>
              )}

              {tab === "message" && (submitted ? (
                <div className="consult-success">
                  <Send className="consult-success-icon" />
                  <h3>Message handed off.</h3>
                  <p>Your mail client just opened with a draft. Hit send and we'll reply within 24 hours.</p>
                  <button className="btn btn-ghost" onClick={() => { setSubmitted(false); setForm({ name: "", email: "", company: "", message: "" }); }}>
                    Send another
                  </button>
                </div>
              ) : (
                <form onSubmit={onSubmit} className="consult-form">
                  <h3 className="consult-card-title">
                    <span className="mono dim">[ TRANSMISSION ]</span>
                    What are you trying to figure out?
                  </h3>

                  <div className="consult-row">
                    <label>
                      <span className="mono dim">NAME</span>
                      <input value={form.name} onChange={onChange("name")} required placeholder="Jane Doe" autoComplete="name" />
                    </label>
                    <label>
                      <span className="mono dim">EMAIL</span>
                      <input type="email" value={form.email} onChange={onChange("email")} required placeholder="jane@company.com" autoComplete="email" />
                    </label>
                  </div>

                  <label>
                    <span className="mono dim">COMPANY</span>
                    <input value={form.company} onChange={onChange("company")} placeholder="Optional" autoComplete="organization" />
                  </label>

                  <label>
                    <span className="mono dim">MESSAGE</span>
                    <textarea
                      value={form.message}
                      onChange={onChange("message")}
                      required
                      rows={5}
                      placeholder="The problem, the goal, the constraint, or just where to start. Whatever's on your mind."
                    />
                  </label>

                  <button type="submit" className="btn btn-primary btn-fx consult-submit">
                    <span className="btn-bracket">[</span>
                    <Send size={14} />
                    Send transmission
                    <span className="btn-bracket">]</span>
                  </button>
                </form>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
