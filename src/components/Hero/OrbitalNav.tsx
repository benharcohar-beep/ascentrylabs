import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import "./orbital.css";

// Section navigation rendered AS satellites around the wireframe core.
// Four labels — Services, Portfolio, About, Testimonials — sit at the
// corners of the core's box, each with a thin glowing line that points
// toward the center. Click to smooth-scroll. On mouse-move we apply a
// gentle 3D parallax tilt to the whole orbital group so the satellites
// feel like they're suspended in space with the core, not stuck on glass.

type Orbit = {
  code: string;
  label: string;
  href: string;
  position: "tl" | "tr" | "bl" | "br";
};

const ORBITS: Orbit[] = [
  { code: "S.02", label: "Services", href: "/services", position: "tl" },
  { code: "P.03", label: "Portfolio", href: "/portfolio", position: "tr" },
  { code: "A.04", label: "About", href: "/about", position: "bl" },
  { code: "T.05", label: "Testimonials", href: "/testimonials", position: "br" },
];

export function OrbitalNav() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;

    let raf = 0;
    let tx = 0, ty = 0, x = 0, y = 0;

    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = (e.clientX - cx) / rect.width;
      const dy = (e.clientY - cy) / rect.height;
      tx = dx * 8;
      ty = dy * 8;
    };

    function tick() {
      x += (tx - x) * 0.06;
      y += (ty - y) * 0.06;
      el!.style.setProperty("--ox", `${x}px`);
      el!.style.setProperty("--oy", `${y}px`);
      raf = requestAnimationFrame(tick);
    }

    window.addEventListener("mousemove", onMove, { passive: true });
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMove);
    };
  }, []);

  return (
    <nav className="orbital-nav" ref={rootRef} aria-label="Section navigation">
      {/* SVG layer with the connecting lines from each label toward center */}
      <svg className="orbital-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
        <defs>
          <linearGradient id="orbit-line-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#7fd1d3" stopOpacity="0.7" />
            <stop offset="60%" stopColor="#7fd1d3" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#7fd1d3" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Each line: from the label's corner toward the center (50,50) */}
        <line x1="14" y1="20" x2="50" y2="50" stroke="url(#orbit-line-grad)" strokeWidth="0.25" />
        <line x1="86" y1="20" x2="50" y2="50" stroke="url(#orbit-line-grad)" strokeWidth="0.25" />
        <line x1="14" y1="80" x2="50" y2="50" stroke="url(#orbit-line-grad)" strokeWidth="0.25" />
        <line x1="86" y1="80" x2="50" y2="50" stroke="url(#orbit-line-grad)" strokeWidth="0.25" />
      </svg>

      {ORBITS.map((o) => (
        <Link key={o.href} to={o.href} className={`orbit orbit-${o.position}`}>
          <span className="orbit-marker" aria-hidden>
            <span className="orbit-marker-dot" />
            <span className="orbit-marker-ring" />
          </span>
          <span className="orbit-text">
            <span className="orbit-code mono">[ {o.code} ]</span>
            <span className="orbit-label">{o.label}</span>
          </span>
        </Link>
      ))}
    </nav>
  );
}
