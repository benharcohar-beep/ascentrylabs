import { useEffect, useState } from "react";
import { NAV_LINKS } from "../../data/nav";
import { Menu, X } from "lucide-react";
import "./nav.css";

// Stripped-down top nav — section links live around the wireframe core
// in OrbitalNav. The header keeps the logo, the primary CTA, and a
// mobile burger that surfaces the section list.
// (Cmd+K shortcut still opens the palette; we just don't surface the
// "⌘K" button — it read as developer jargon to non-technical visitors.)
export function Nav() {
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

          <div className="nav-actions">
            <a href="#consult" className="btn btn-primary btn-fx nav-cta">
              <span className="btn-bracket">[</span>
              Schedule Consultation
              <span className="btn-bracket">]</span>
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
          <a href="#consult" className="btn btn-primary btn-fx" onClick={() => setMobileOpen(false)}>
            <span className="btn-bracket">[</span>
            Schedule Consultation
            <span className="btn-bracket">]</span>
          </a>
        </div>
      )}
    </>
  );
}
