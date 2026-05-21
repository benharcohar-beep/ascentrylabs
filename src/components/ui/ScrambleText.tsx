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
 *   - background tabs: timing uses Date.now() + setInterval fallback so
 *     the scramble completes correctly even when rAF is throttled, and
 *     it re-fires when the tab becomes visible again
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
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setOut(text);
      return;
    }

    const start = () => {
      if (startedRef.current) return;
      startedRef.current = true;
      cancelRef.current = runScramble();
    };

    // If the tab is hidden right now, defer the start until it becomes
    // visible (don't bail permanently — that left content stuck on placeholder).
    const onVisStart = () => {
      if (!document.hidden) {
        document.removeEventListener("visibilitychange", onVisStart);
        if (!triggerOnView) start();
        // If triggerOnView is set, the IntersectionObserver below handles it
      }
    };
    if (document.hidden) {
      document.addEventListener("visibilitychange", onVisStart);
    }

    if (!triggerOnView) {
      if (!document.hidden) start();
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
        document.removeEventListener("visibilitychange", onVisStart);
        cancelRef.current?.();
      };
    }
    return () => {
      document.removeEventListener("visibilitychange", onVisStart);
      cancelRef.current?.();
    };
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

    // Belt-and-braces interval — fires even in background tabs (~1s min).
    // Date.now()-based timing means progress is correct whether step is
    // called every 16ms (foreground) or every 1000ms (background).
    interval = window.setInterval(step, 80);

    function cleanup() {
      cancelled = true;
      cancelAnimationFrame(raf);
      clearInterval(interval);
    }

    return cleanup;
  }

  return (
    <span ref={ref} className={className} aria-label={text}>
      {out}
    </span>
  );
}
