import { useEffect, useRef } from "react";
import type { ReactNode, AnchorHTMLAttributes, ButtonHTMLAttributes } from "react";

type CommonProps = {
  children: ReactNode;
  /** 0..1 — how far the element shifts toward the cursor (default 0.18). Subtle is better. */
  strength?: number;
  /** px — engagement radius beyond the element's bounding box */
  radius?: number;
  /** px — hard cap on displacement in any direction so adjacent buttons can't overlap */
  maxOffset?: number;
  className?: string;
};

type AsAnchor = CommonProps & { href: string } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof CommonProps>;
type AsButton = CommonProps & { href?: undefined } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof CommonProps>;
type Props = AsAnchor | AsButton;

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

export function MagneticButton(props: Props) {
  const { children, strength = 0.18, radius = 90, maxOffset = 10, className, ...rest } = props;
  const ref = useRef<HTMLElement>(null);
  const innerRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Skip on coarse pointer (touch) — magnetic adds nothing on touch and
    // can cause jank on tap.
    if (!window.matchMedia("(pointer: fine)").matches) return;

    let raf = 0;
    let tx = 0, ty = 0, x = 0, y = 0;

    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;

      // Only engage when the cursor is actually inside or near the element.
      // We use a tight radius so adjacent buttons don't fight over the cursor.
      const halfW = rect.width / 2;
      const halfH = rect.height / 2;
      const inside =
        Math.abs(dx) < halfW + radius && Math.abs(dy) < halfH + radius;

      if (inside) {
        tx = clamp(dx * strength, -maxOffset, maxOffset);
        ty = clamp(dy * strength, -maxOffset, maxOffset);
      } else {
        tx = 0;
        ty = 0;
      }
    };

    const onLeave = () => {
      tx = 0;
      ty = 0;
    };

    function tick() {
      x += (tx - x) * 0.18;
      y += (ty - y) * 0.18;
      // Snap small residuals to 0 so the element returns cleanly to rest
      if (Math.abs(x) < 0.05 && Math.abs(tx) === 0) x = 0;
      if (Math.abs(y) < 0.05 && Math.abs(ty) === 0) y = 0;
      el!.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      if (innerRef.current) {
        innerRef.current.style.transform = `translate3d(${x * 0.35}px, ${y * 0.35}px, 0)`;
      }
      raf = requestAnimationFrame(tick);
    }

    window.addEventListener("mousemove", onMove, { passive: true });
    el.addEventListener("mouseleave", onLeave);
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, [strength, radius, maxOffset]);

  if ("href" in props && props.href !== undefined) {
    const { href, ...anchorRest } = rest as AnchorHTMLAttributes<HTMLAnchorElement>;
    return (
      <a
        ref={ref as React.RefObject<HTMLAnchorElement>}
        href={href}
        className={className}
        style={{ display: "inline-flex", willChange: "transform" }}
        {...anchorRest}
      >
        <span ref={innerRef} style={{ display: "inline-flex", alignItems: "center", gap: "0.6rem", willChange: "transform" }}>
          {children}
        </span>
      </a>
    );
  }
  const buttonRest = rest as ButtonHTMLAttributes<HTMLButtonElement>;
  return (
    <button
      ref={ref as React.RefObject<HTMLButtonElement>}
      className={className}
      style={{ display: "inline-flex", willChange: "transform" }}
      {...buttonRest}
    >
      <span ref={innerRef} style={{ display: "inline-flex", alignItems: "center", gap: "0.6rem", willChange: "transform" }}>
        {children}
      </span>
    </button>
  );
}
