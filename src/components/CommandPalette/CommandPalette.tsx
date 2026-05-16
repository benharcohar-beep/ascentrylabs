import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Search, ArrowRight, Mail, Calendar, Briefcase, Users, Star, Box, FileText, Layers, Phone, Send } from "lucide-react";
import { CONTACT_EMAIL } from "../../data/nav";
import "./palette.css";

type Cmd = {
  id: string;
  label: string;
  hint?: string;
  group: string;
  icon: React.ReactNode;
  action: () => void;
};

type Props = {
  open: boolean;
  onClose: () => void;
};

export function CommandPalette({ open, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const commands: Cmd[] = useMemo(() => {
    const go = (path: string) => () => {
      onClose();
      setTimeout(() => navigate(path), 60);
    };
    return [
      { id: "home", label: "Home", hint: "Hero · orbital nav · core", group: "Navigate", icon: <Box size={16} />, action: go("/") },
      { id: "services", label: "Services", hint: "Six ways we work together", group: "Navigate", icon: <Box size={16} />, action: go("/services") },
      { id: "portfolio", label: "Portfolio", hint: "Selected work", group: "Navigate", icon: <Layers size={16} />, action: go("/portfolio") },
      { id: "about", label: "About", hint: "Hunter Sandidge & Ascentry Labs", group: "Navigate", icon: <Users size={16} />, action: go("/about") },
      { id: "testimonials", label: "Testimonials", hint: "Words from people I've worked with", group: "Navigate", icon: <Star size={16} />, action: go("/testimonials") },
      { id: "consult", label: "Schedule consultation", hint: "Free 30-min call", group: "Actions", icon: <Calendar size={16} />, action: go("/#consult") },
      { id: "email", label: "Email Hunter directly", hint: CONTACT_EMAIL, group: "Actions", icon: <Mail size={16} />, action: () => { window.location.href = `mailto:${CONTACT_EMAIL}`; onClose(); } },
      { id: "case", label: "View case studies", hint: "Featured work in portfolio", group: "Actions", icon: <FileText size={16} />, action: go("/portfolio") },
      { id: "hire", label: "Discuss a project", hint: "Custom development & advisory", group: "Actions", icon: <Briefcase size={16} />, action: go("/#consult") },
      { id: "send", label: "Send a transmission", hint: "Jump straight to the contact form", group: "Quick", icon: <Send size={16} />, action: go("/#consult") },
      { id: "phone", label: "Talk to a human", hint: "Free 30-min consultation", group: "Quick", icon: <Phone size={16} />, action: go("/#consult") },
    ];
  }, [navigate, onClose]);

  const filtered = useMemo(() => {
    if (!query) return commands;
    const q = query.toLowerCase();
    return commands.filter(
      (c) => c.label.toLowerCase().includes(q) || (c.hint?.toLowerCase().includes(q) ?? false)
    );
  }, [query, commands]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    setTimeout(() => inputRef.current?.focus(), 50);
    // Tell other floating dialogs to close so the palette owns focus.
    window.dispatchEvent(new CustomEvent("ascentry:dialog-open", { detail: { source: "command-palette" } }));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((a) => Math.min(filtered.length - 1, a + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => Math.max(0, a - 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        filtered[active]?.action();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, filtered, active, onClose]);

  // Group by section
  const grouped = useMemo(() => {
    const map = new Map<string, Cmd[]>();
    filtered.forEach((c) => {
      if (!map.has(c.group)) map.set(c.group, []);
      map.get(c.group)!.push(c);
    });
    return Array.from(map.entries());
  }, [filtered]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="palette-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />
          <motion.div
            className="palette glass"
            initial={{ opacity: 0, y: -16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.96 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            role="dialog"
            aria-label="Command palette"
          >
            <div className="palette-search">
              <Search size={16} className="palette-search-icon" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => { setQuery(e.target.value); setActive(0); }}
                placeholder="Type a command or search..."
                spellCheck={false}
                autoComplete="off"
              />
              <span className="mono dim palette-kbd">ESC</span>
            </div>

            <div className="palette-list">
              {grouped.length === 0 && (
                <div className="palette-empty">
                  <span className="mono dim">No results for "{query}"</span>
                </div>
              )}
              {grouped.map(([group, items]) => (
                <div key={group} className="palette-group">
                  <div className="palette-group-label mono dim">{group}</div>
                  {items.map((c) => {
                    const idx = filtered.indexOf(c);
                    const isActive = idx === active;
                    return (
                      <button
                        key={c.id}
                        className={`palette-item ${isActive ? "is-active" : ""}`}
                        onClick={c.action}
                        onMouseEnter={() => setActive(idx)}
                      >
                        <span className="palette-item-icon">{c.icon}</span>
                        <span className="palette-item-label">{c.label}</span>
                        {c.hint && <span className="palette-item-hint dim">{c.hint}</span>}
                        <ArrowRight size={14} className="palette-item-arrow" />
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>

            <div className="palette-foot">
              <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
              <span><kbd>↵</kbd> select</span>
              <span><kbd>esc</kbd> close</span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
