import { useEffect, useRef, useState } from "react";

const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%&*+=<>/?";

type Props = {
  text: string;
  className?: string;
  triggerOnView?: boolean;
  durationMs?: number;
  delayMs?: number;
};

export function ScrambleText({ text, className, triggerOnView = true, durationMs = 1400, delayMs = 0 }: Props) {
  const [out, setOut] = useState(text.replace(/[^\s]/g, "·"));
  const ref = useRef<HTMLSpanElement>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!triggerOnView) {
      runScramble();
      return;
    }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !startedRef.current) {
          startedRef.current = true;
          runScramble();
        }
      },
      { threshold: 0.4 }
    );
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  function runScramble() {
    const start = performance.now() + delayMs;
    const end = start + durationMs;
    let raf = 0;

    const tick = (t: number) => {
      if (t < start) {
        raf = requestAnimationFrame(tick);
        return;
      }
      const progress = Math.min(1, (t - start) / durationMs);
      // ease — slow start, fast finish
      const eased = progress * progress;
      const revealCount = Math.floor(eased * text.length);
      let next = "";
      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (i < revealCount || ch === " ") {
          next += ch;
        } else {
          if (ch === "." || ch === "," || ch === "!" || ch === "?") {
            next += ch;
          } else {
            next += CHARS[Math.floor(Math.random() * CHARS.length)];
          }
        }
      }
      setOut(next);
      if (t < end) {
        raf = requestAnimationFrame(tick);
      } else {
        setOut(text);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }

  return (
    <span ref={ref} className={className} aria-label={text}>
      {out}
    </span>
  );
}
