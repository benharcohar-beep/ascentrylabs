import { NAV_LINKS, CONTACT_EMAIL } from "../../data/nav";
import "./footer.css";

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="footer">
      <div className="container footer-inner">
        <div className="footer-brand">
          <div className="footer-logo">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M12 2 L22 20 L12 16 L2 20 Z" />
              <circle cx="12" cy="11" r="1.6" fill="currentColor" />
            </svg>
            <span>Ascentry Labs</span>
          </div>
          <p className="footer-tagline">
            AI &amp; digital transformation consulting for organizations that can't afford ambiguity.
          </p>
        </div>

        <nav className="footer-links">
          <div className="footer-col">
            <h4 className="mono dim">EXPLORE</h4>
            {NAV_LINKS.map((l) => (
              <a key={l.href} href={l.href}>{l.label}</a>
            ))}
          </div>
          <div className="footer-col">
            <h4 className="mono dim">CONTACT</h4>
            <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
            <a href="#consult">Schedule consultation</a>
          </div>
          <div className="footer-col">
            <h4 className="mono dim">STATUS</h4>
            <span className="footer-status">
              <span className="footer-status-dot" />
              All systems nominal
            </span>
            <span className="dim mono">v2.0 · {year}</span>
          </div>
        </nav>
      </div>

      <div className="footer-bottom container">
        <span className="mono dim">© {year} Ascentry Labs · All rights reserved</span>
        <span className="mono dim">Built among the stars</span>
      </div>
    </footer>
  );
}
