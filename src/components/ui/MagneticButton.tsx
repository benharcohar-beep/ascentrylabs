import { useEffect, useRef } from "react";
import type { ReactNode, AnchorHTMLAttributes, ButtonHTMLAttributes } from "react";

type CommonProps = {
  children: ReactNode;
  strength?: number;       // 0..1 — how far the element shifts (default 0.35)
  radius?: number;         // px — when within radius it engages
  className?: string;
};

type AsAnchor = CommonProps & { href: string } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof CommonProps>;
type AsButton = CommonProps & { href?: undefined } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof CommonProps>;
type Props = AsAnchor | AsButton;

export function MagneticButton(props: Props) {
  const { children, strength = 0.35, radius = 120, className, ...rest } = props;
  const ref = useRef<HTMLElement>(null);
  const innerRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    let tx = 0, ty = 0, x = 0, y = 0;
    let active = false;

    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const dist = Math.hypot(dx, dy);
      if (dist < radius + Math.max(rect.width, rect.height) / 2) {
        active = true;
        tx = dx * strength;
        ty = dy * strength;
      } else if (active) {
        active = false;
        tx = 0;
        ty = 0;
      }
    };

    const onLeave = () => {
      active = false;
      tx = 0;
      ty = 0;
    };

    function tick() {
      x += (tx - x) * 0.18;
      y += (ty - y) * 0.18;
      el!.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      if (innerRef.current) {
        innerRef.current.style.transform = `translate3d(${x * 0.4}px, ${y * 0.4}px, 0)`;
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
  }, [strength, radius]);

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
