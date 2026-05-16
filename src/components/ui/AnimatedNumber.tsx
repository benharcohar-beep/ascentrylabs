import { useEffect, useRef, useState } from "react";

type Props = {
  value: string;          // e.g. "15+", "$10B+", "170+", "ISS"
  durationMs?: number;
  className?: string;
};

// Counts a number up from 0 to its target when it scrolls into view.
// Preserves any prefix (e.g. "$") and suffix (e.g. "B+", "+"). If the
// value contains no digits (e.g. "ISS") we just render it as-is.
//
// IntersectionObserver gate keeps this cheap on long pages — only the
// stats that come into view actually animate, and only once.
export function AnimatedNumber({ value, durationMs = 1500, className }: Props) {
  const [out, setOut] = useState(() => makeInitial(value));
  const ref = useRef<HTMLSpanElement>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setOut(value);
      return;
    }
    const parsed = parseValue(value);
    if (!parsed) {
      setOut(value);
      return;
    }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !startedRef.current) {
          startedRef.current = true;
          io.disconnect();
          animate(parsed);
        }
      },
      { threshold: 0.4 }
    );
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  function animate({ prefix, target, suffix }: { prefix: string; target: number; suffix: string }) {
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / durationMs);
      // Ease-out cubic — fast start, smooth landing
      const eased = 1 - Math.pow(1 - k, 3);
      const n = Math.round(target * eased);
      setOut(`${prefix}${n}${suffix}`);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }

  return (
    <span ref={ref} className={className}>
      {out}
    </span>
  );
}

function parseValue(v: string): { prefix: string; target: number; suffix: string } | null {
  // Capture optional prefix + digits + optional suffix
  const m = v.match(/^(\D*?)(\d+)(.*)$/);
  if (!m) return null;
  return { prefix: m[1], target: parseInt(m[2], 10), suffix: m[3] };
}

function makeInitial(v: string): string {
  // Show 0 as the starting value when we'll animate, preserving prefix/suffix.
  const parsed = parseValue(v);
  if (!parsed) return v;
  return `${parsed.prefix}0${parsed.suffix}`;
}
