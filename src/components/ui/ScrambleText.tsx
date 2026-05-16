import { useEffect, useRef, useState } from "react";

const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%&*+=<>/?";

type Props = {
  text: string;
  className?: string;
  /** If true, wait for the element to enter the viewport before scrambling. */
  triggerOnView?: boolean;
  durationMs?: number;
  delayMs?: number;
};

/**
 * Glyph-decode reveal: text starts as scrambled chars and resolves to the
 * real string over `durationMs`. Robust to:
 *   - prefers-reduced-motion (skips, shows final text)
 *   - background tabs (rAF throttled): uses an interval fallback so the
 *     scramble still ticks (slowly) and a visibility listener that snaps
 *     to final text if the tab is hidden when the animation should run
 */
export function ScrambleText({
  text,
  className,
  triggerOnView = true,
  durationMs = 1400,
  delayMs = 0,
}: Props) {
  const placeholder = text.replace(/[^\s]/g, "·");
  const [out, setOut] = useState(placeholder);
  const ref = useRef<HTMLSpanElement>(null);
  const startedRef = useRef(false);
  const cancelRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || document.hidden) {
      setOut(text);
      return;
    }

    const start = () => {
      if (startedRef.current) return;
      startedRef.current = true;
      cancelRef.current = runScramble();
    };

    if (!triggerOnView) {
      start();
    } else {
      const el = ref.current;
      if (!el) return;
      const io = new IntersectionObserver(
        (entries) => { if (entries[0].isIntersecting) start(); },
        { threshold: 0.1 }
      );
      io.observe(el);
      return () => {
        io.disconnect();
        cancelRef.current?.();
      };
    }
    return () => cancelRef.current?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  function runScramble() {
    const startAt = Date.now() + delayMs;
    const endAt = startAt + durationMs;
    let cancelled = false;
    let raf = 0;
    let interval = 0;

    const step = () => {
      if (cancelled) return;
      const now = Date.now();
      if (now < startAt) return;
      if (document.hidden) {
        // Tab not visible - jump straight to final to avoid showing mid-scramble
        setOut(text);
        cleanup();
        return;
      }
      const progress = Math.min(1, (now - startAt) / durationMs);
      const eased = progress * progress;
      const revealCount = Math.floor(eased * text.length);
      let next = "";
      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (i < revealCount || ch === " ") next += ch;
        else if (/[.,!?;:'"()-]/.test(ch)) next += ch;
        else next += CHARS[Math.floor(Math.random() * CHARS.length)];
      }
      setOut(next);
      if (now >= endAt) {
        setOut(text);
        cleanup();
      }
    };

    const tick = () => {
      step();
      if (!cancelled) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    // Belt-and-braces interval (fires even in background tabs at min 1s)
    interval = window.setInterval(step, 80);

    // If the tab becomes hidden mid-anim, snap to final
    const onVis = () => {
      if (document.hidden) {
        setOut(text);
        cleanup();
      }
    };
    document.addEventListener("visibilitychange", onVis);

    function cleanup() {
      cancelled = true;
      cancelAnimationFrame(raf);
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVis);
    }

    return cleanup;
  }

  return (
    <span ref={ref} className={className} aria-label={text}>
      {out}
    </span>
  );
}
