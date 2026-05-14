import { useEffect, useRef, useState } from "react";
import "./boot.css";

// A sub-2-second boot intro that fires once per session. Reads as a
// mission-control sequence — terminal lines, a progress bar, then a
// graceful fade-out into the live page.
//
// Skippable with any key/click. Skipped entirely on:
//   - prefers-reduced-motion
//   - already shown this session (sessionStorage key)

const SS_KEY = "ascentry-boot-shown-v1";

const LINES: { text: string; delay: number }[] = [
  { text: "ASCENTRY OS · v2.0", delay: 0 },
  { text: "[ OK ] Cold-boot starfield rendering pipeline", delay: 180 },
  { text: "[ OK ] Loading neural core geometry (subdivision 4)", delay: 320 },
  { text: "[ OK ] Calibrating reticle · pointer = fine", delay: 480 },
  { text: "[ OK ] Establishing uplink to ascentrylabs.com", delay: 640 },
  { text: "[ READY ] Welcome.", delay: 880 },
];

export function BootSequence() {
  const [visible, setVisible] = useState(false);
  const [revealed, setRevealed] = useState(0);
  const [progress, setProgress] = useState(0);
  const [fading, setFading] = useState(false);
  const skipRef = useRef(false);

  useEffect(() => {
    // Honor reduced motion + don't replay within a session
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    try {
      if (sessionStorage.getItem(SS_KEY)) return;
      sessionStorage.setItem(SS_KEY, "1");
    } catch { /* ignore (private mode) */ }

    setVisible(true);
    document.body.classList.add("boot-active");

    // Reveal lines one at a time
    LINES.forEach((line, i) => {
      setTimeout(() => {
        if (skipRef.current) return;
        setRevealed(i + 1);
      }, line.delay);
    });

    // Drive the progress bar over the full duration
    const total = 1200;
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / total);
      setProgress(p);
      if (p < 1 && !skipRef.current) raf = requestAnimationFrame(tick);
      else finish();
    };
    raf = requestAnimationFrame(tick);

    function cleanupListeners() {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("click", onClick);
    }

    function finish() {
      // Detach skip listeners as soon as the boot wraps up so they don't
      // intercept clicks/keystrokes on the live page (e.g. portfolio
      // card opens) after boot has visually disappeared.
      cleanupListeners();
      setFading(true);
      setTimeout(() => {
        setVisible(false);
        document.body.classList.remove("boot-active");
      }, 600);
    }

    function skip() {
      if (skipRef.current) return;
      skipRef.current = true;
      cancelAnimationFrame(raf);
      finish();
    }

    const onKey = () => skip();
    const onClick = () => skip();
    window.addEventListener("keydown", onKey);
    window.addEventListener("click", onClick);

    return () => {
      cancelAnimationFrame(raf);
      cleanupListeners();
      document.body.classList.remove("boot-active");
    };
  }, []);

  if (!visible) return null;

  return (
    <div className={`boot ${fading ? "is-fading" : ""}`} role="status" aria-live="polite">
      <div className="boot-inner">
        <div className="boot-logo" aria-hidden>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path d="M12 2 L22 20 L12 16 L2 20 Z" />
            <circle cx="12" cy="11" r="1.6" fill="currentColor" />
          </svg>
        </div>

        <pre className="boot-lines">
          {LINES.slice(0, revealed).map((line, i) => (
            <div key={i} className="boot-line">
              <span className="boot-cursor">›</span> {line.text}
            </div>
          ))}
          {revealed < LINES.length && (
            <div className="boot-line boot-line-cursor"><span className="boot-cursor">›</span> <span className="boot-blink">█</span></div>
          )}
        </pre>

        <div className="boot-bar" aria-hidden>
          <div className="boot-bar-fill" style={{ transform: `scaleX(${progress})` }} />
        </div>

        <div className="boot-skip mono dim">PRESS ANY KEY TO SKIP</div>
      </div>
    </div>
  );
}
