import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import "./consultcta.css";

// Compact consultation CTA banner used at the bottom of inner pages.
// Points the user back to the home page's consult form section.
export function ConsultCta() {
  return (
    <section className="consult-cta-section" aria-label="Schedule a consultation">
      <div className="container">
        <div className="consult-cta glass">
          <div className="consult-cta-corners" aria-hidden>
            <span /><span /><span /><span />
          </div>
          <div className="consult-cta-body">
            <div className="mono consult-cta-eyebrow">FREE · 30 MIN · NO PITCH</div>
            <h2 className="consult-cta-title">Ready to bring your company into the era of AI?</h2>
            <p className="consult-cta-text">
              Honest conversation about where you are and what's next. NDA available on request.
            </p>
          </div>
          <div className="consult-cta-actions">
            <Link to="/#consult" className="btn btn-primary btn-fx">
              <span className="btn-bracket">[</span>
              Schedule consultation
              <span className="btn-bracket">]</span>
              <ArrowUpRight size={14} className="arrow" />
            </Link>
            <Link to="/" className="btn btn-ghost btn-fx">
              <span className="btn-bracket">[</span>
              Back to home
              <span className="btn-bracket">]</span>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
