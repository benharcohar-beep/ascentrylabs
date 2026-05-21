import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import { ScrambleText } from "../ui/ScrambleText";
import { OrbitalNav } from "./OrbitalNav";
import { ArrowUpRight, ArrowRight } from "lucide-react";
import "./hero.css";

// Three.js + R3F is ~800KB. Lazy-load it so first paint isn't blocked on
// the WebGL canvas.
const WireframeCore = lazy(() =>
  import("./WireframeCore").then((m) => ({ default: m.WireframeCore }))
);

function CoreFallback() {
  return (
    <div className="wireframe-core wireframe-core-loading">
      <div className="wireframe-core-pulse" aria-hidden />
      <div className="wireframe-halo" aria-hidden />
    </div>
  );
}

export function Hero() {
  // Hero entrances are pure CSS keyframes (.hero-reveal). CSS animations
  // pause when the tab is hidden and resume on visibility - no JS
  // safeguard needed. The previous `.no-anim` skip-on-hidden trick was
  // over-aggressive: it permanently disabled the reveals if the tab
  // happened to be hidden on first paint, even after the user came back.

  return (
    <section className="hero" id="top">
      <div className="container hero-inner">
        <div className="hero-left">
          <div className="eyebrow hero-reveal" style={{ animationDelay: "0.1s" }}>
            <span className="mono">ASCENTRY OS · v2.0 · ONLINE</span>
          </div>

          <h1 className="hero-title">
            <span className="hero-title-line hero-reveal" style={{ animationDelay: "0.22s" }}>
              <ScrambleText text="Bring your company" durationMs={1100} />
            </span>
            <span className="hero-title-line hero-reveal" style={{ animationDelay: "0.34s" }}>
              <ScrambleText text="into the era of " durationMs={1300} delayMs={200} />
              <span className="hero-accent">
                <ScrambleText text="AI." durationMs={900} delayMs={1100} />
              </span>
            </span>
          </h1>

          <p className="hero-sub hero-reveal" style={{ animationDelay: "0.46s" }}>
            Fragmented ERPs and data providers, hours lost to Excel wrangling, no real-time view of performance,
            and a creeping sense of falling behind: most companies know they need AI but don't know where to start.
          </p>

          <p className="hero-sub hero-reveal" style={{ animationDelay: "0.58s" }}>
            Ascentry Labs closes that gap. Founded by <strong>Hunter Sandidge</strong> - the engineer behind the
            AI and analytics ecosystem that monitors life support on the International Space Station, father of the
            AI copilot for the xEVAS spacesuit, and smart-factory and digital transformation lead at a Fortune&nbsp;100 -
            Ascentry Labs translates the noise around AI into systems that actually run your operation.
          </p>

          <div className="hero-cta hero-reveal" style={{ animationDelay: "0.7s" }}>
            <a href="#consult" className="btn btn-primary btn-fx">
              <span className="btn-bracket">[</span>
              Free 30-min Consultation
              <span className="btn-bracket">]</span>
              <ArrowUpRight size={16} className="arrow" />
            </a>
            <Link to="/services" className="btn btn-ghost btn-fx">
              <span className="btn-bracket">[</span>
              See how we help
              <span className="btn-bracket">]</span>
              <ArrowRight size={16} className="arrow" />
            </Link>
          </div>

          <div className="hero-meta hero-reveal" style={{ animationDelay: "0.82s" }}>
            <div className="hero-meta-item">
              <span className="mono dim">CLIENTS</span>
              <span>NASA · Collins Aerospace · Marquette</span>
            </div>
            <div className="hero-meta-item">
              <span className="mono dim">SECTORS</span>
              <span>Aerospace · Defense · Finance · Education</span>
            </div>
          </div>
        </div>

        <div className="hero-right hero-reveal-fade">
          <Suspense fallback={<CoreFallback />}>
            <WireframeCore />
          </Suspense>
          <OrbitalNav />
        </div>
      </div>

      <div className="hero-scroll-hint">
        <span className="mono dim">SCROLL</span>
        <span className="hero-scroll-bar" aria-hidden />
      </div>
    </section>
  );
}
