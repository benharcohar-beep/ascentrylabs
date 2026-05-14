import { useEffect } from "react";
import Lenis from "lenis";

// Inertial smooth scroll wrapper. Hijacks the wheel + scrollbar so the
// page glides instead of snapping. Disabled when the user prefers
// reduced motion. Also intercepts hash-anchor clicks so #services etc.
// scroll smoothly through Lenis rather than the browser default.
export function useSmoothScroll() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const lenis = new Lenis({
      duration: 1.1,
      easing: (t) => 1 - Math.pow(1 - t, 3),
      smoothWheel: true,
      lerp: 0.1,
      gestureOrientation: "vertical",
    });

    let raf = 0;
    function tick(time: number) {
      lenis.raf(time);
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);

    // Intercept anchor clicks
    const onAnchorClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const a = target.closest('a[href^="#"]') as HTMLAnchorElement | null;
      if (!a) return;
      const href = a.getAttribute("href");
      if (!href || href === "#") return;
      const el = document.querySelector(href) as HTMLElement | null;
      if (!el) return;
      e.preventDefault();
      lenis.scrollTo(el, { offset: -64, duration: 1.2 });
    };
    document.addEventListener("click", onAnchorClick);

    // Programmatic helper — let other code (CommandPalette) trigger smooth scroll
    (window as Window & { __lenis?: Lenis }).__lenis = lenis;

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("click", onAnchorClick);
      lenis.destroy();
      delete (window as Window & { __lenis?: Lenis }).__lenis;
    };
  }, []);
}
