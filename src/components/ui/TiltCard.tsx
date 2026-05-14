import { useRef } from "react";
import type { ReactNode, CSSProperties } from "react";

type Props = {
  children: ReactNode;
  className?: string;
  intensity?: number;   // degrees of tilt at full extent
  glare?: boolean;
  style?: CSSProperties;
};

export function TiltCard({ children, className, intensity = 6, glare = true, style }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const glareRef = useRef<HTMLDivElement>(null);

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;   // 0..1
    const y = (e.clientY - rect.top) / rect.height;
    const rx = (0.5 - y) * intensity;
    const ry = (x - 0.5) * intensity;
    el.style.setProperty("--tilt-rx", `${rx}deg`);
    el.style.setProperty("--tilt-ry", `${ry}deg`);
    el.style.setProperty("--tilt-z", `8px`);
    if (glareRef.current) {
      glareRef.current.style.background = `radial-gradient(circle at ${x * 100}% ${y * 100}%, rgba(174, 245, 248, 0.18), transparent 45%)`;
      glareRef.current.style.opacity = "1";
    }
  };

  const onLeave = () => {
    const el = ref.current;
    if (!el) return;
    el.style.setProperty("--tilt-rx", `0deg`);
    el.style.setProperty("--tilt-ry", `0deg`);
    el.style.setProperty("--tilt-z", `0px`);
    if (glareRef.current) glareRef.current.style.opacity = "0";
  };

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className={className}
      style={{
        transformStyle: "preserve-3d",
        transform: "perspective(900px) rotateX(var(--tilt-rx, 0deg)) rotateY(var(--tilt-ry, 0deg)) translateZ(var(--tilt-z, 0px))",
        transition: "transform 0.35s var(--ease-out-quart)",
        willChange: "transform",
        ...style,
      }}
    >
      {children}
      {glare && (
        <div
          ref={glareRef}
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            opacity: 0,
            transition: "opacity 0.3s var(--ease-out-quart)",
            borderRadius: "inherit",
            mixBlendMode: "screen",
          }}
        />
      )}
    </div>
  );
}
