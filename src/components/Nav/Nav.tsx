import { useEffect, useState } from "react";
import { NAV_LINKS } from "../../data/nav";
import { Command, Menu, X } from "lucide-react";
import "./nav.css";

type Props = {
  onOpenPalette: () => void;
};

export function Nav({ onOpenPalette }: Props) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      <header className={`nav ${scrolled ? "is-scrolled" : ""}`}>
        <div className="container nav-inner">
          <a href="#top" className="nav-logo" aria-label="Ascentry Labs home">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M12 2 L22 20 L12 16 L2 20 Z" />
              <circle cx="12" cy="11" r="1.6" fill="currentColor" />
            </svg>
            <span className="nav-logo-text">Ascentry Labs</span>
          </a>

          <nav className="nav-links" aria-label="Primary">
            {NAV_LINKS.map((l) => (
              <a key={l.href} href={l.href}>{l.label}</a>
            ))}
          </nav>

          <div className="nav-actions">
            <button
              className="nav-cmd"
              onClick={onOpenPalette}
              aria-label="Open command palette"
              title="Command palette (⌘K)"
            >
              <Command size={14} />
              <span className="mono">K</span>
            </button>
            <a href="#consult" className="btn btn-primary nav-cta">
              Schedule Consultation
              <span className="arrow">↗</span>
            </a>
            <button
              className="nav-burger"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileOpen}
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
      </header>

      {mobileOpen && (
        <div className="nav-mobile glass" role="dialog" aria-label="Mobile navigation">
          {NAV_LINKS.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setMobileOpen(false)}>
              {l.label}
            </a>
          ))}
          <a href="#consult" className="btn btn-primary" onClick={() => setMobileOpen(false)}>
            Schedule Consultation
          </a>
        </div>
      )}
    </>
  );
}
