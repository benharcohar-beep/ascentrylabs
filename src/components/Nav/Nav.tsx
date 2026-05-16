import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Menu, X } from "lucide-react";
import "./nav.css";

type Props = {
  /** When true (inner pages), show the section links in the header.
      On home (false) the orbital nav around the core serves that purpose. */
  showSectionLinks?: boolean;
};

const SECTION_LINKS = [
  { to: "/services", label: "Services" },
  { to: "/portfolio", label: "Portfolio" },
  { to: "/about", label: "About" },
  { to: "/testimonials", label: "Testimonials" },
];

export function Nav({ showSectionLinks = false }: Props) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Route to home → consult section
  const goConsult = (e: React.MouseEvent) => {
    e.preventDefault();
    setMobileOpen(false);
    navigate("/#consult");
  };

  return (
    <>
      <header className={`nav ${scrolled ? "is-scrolled" : ""}`}>
        <div className="container nav-inner">
          <Link to="/" className="nav-logo" aria-label="Ascentry Labs home">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M12 2 L22 20 L12 16 L2 20 Z" />
              <circle cx="12" cy="11" r="1.6" fill="currentColor" />
            </svg>
            <span className="nav-logo-text">Ascentry Labs</span>
          </Link>

          {showSectionLinks && (
            <nav className="nav-links" aria-label="Primary">
              {SECTION_LINKS.map((l) => (
                <Link key={l.to} to={l.to}>{l.label}</Link>
              ))}
            </nav>
          )}

          <div className="nav-actions">
            <a href="/#consult" onClick={goConsult} className="btn btn-primary btn-fx nav-cta">
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
          {SECTION_LINKS.map((l) => (
            <Link key={l.to} to={l.to} onClick={() => setMobileOpen(false)}>
              {l.label}
            </Link>
          ))}
          <a href="/#consult" onClick={goConsult} className="btn btn-primary btn-fx">
            <span className="btn-bracket">[</span>
            Schedule Consultation
            <span className="btn-bracket">]</span>
          </a>
        </div>
      )}
    </>
  );
}
