import { useEffect, useRef } from "react";

type Star = {
  x: number;
  y: number;
  z: number;        // depth 0..1 — closer = brighter & faster parallax
  r: number;        // radius
  baseAlpha: number;
  twinkle: number;  // phase offset
  twinkleSpeed: number;
  hue: number;      // 0..360 — most stars near 200 (cool white)
};

type Shooter = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
};

const STAR_COUNT = 320;          // total
const SHOOTER_INTERVAL = 9000;   // ms between attempts
const SHOOTER_CHANCE = 0.55;     // probability per attempt

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

export function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | undefined>(undefined);
  const starsRef = useRef<Star[]>([]);
  const shootersRef = useRef<Shooter[]>([]);
  const mouseRef = useRef({ x: 0, y: 0, tx: 0, ty: 0 });
  const lastShooterRef = useRef(0);
  const reducedMotion = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    reducedMotion.current = mq.matches;
    const onMq = (e: MediaQueryListEvent) => (reducedMotion.current = e.matches);
    mq.addEventListener("change", onMq);

    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = window.innerWidth;
    let height = window.innerHeight;

    function regen() {
      const stars: Star[] = [];
      // mobile gets fewer stars
      const count = window.innerWidth < 700 ? Math.floor(STAR_COUNT * 0.55) : STAR_COUNT;
      for (let i = 0; i < count; i++) {
        const z = Math.pow(Math.random(), 1.6); // bias to small/distant
        stars.push({
          x: Math.random() * width,
          y: Math.random() * height,
          z,
          r: rand(0.3, 1.6) * (0.6 + z * 1.4),
          baseAlpha: rand(0.35, 1.0) * (0.4 + z * 0.6),
          twinkle: Math.random() * Math.PI * 2,
          twinkleSpeed: rand(0.4, 1.4),
          hue: Math.random() < 0.85 ? rand(195, 215) : rand(35, 55), // mostly cool, a few golden
        });
      }
      starsRef.current = stars;
    }

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      canvas!.style.width = width + "px";
      canvas!.style.height = height + "px";
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      regen();
    }

    function spawnShooter() {
      // diagonal streak from upper-left to lower-right (varied)
      const fromTop = Math.random() < 0.5;
      const x = fromTop ? rand(-50, width * 0.4) : -50;
      const y = fromTop ? -50 : rand(0, height * 0.6);
      const angle = rand(Math.PI * 0.18, Math.PI * 0.32);
      const speed = rand(8, 14);
      shootersRef.current.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 0,
        maxLife: rand(60, 110),
      });
    }

    let last = performance.now();
    function frame(t: number) {
      const dt = Math.min(50, t - last);
      last = t;

      // smooth mouse parallax target
      mouseRef.current.x += (mouseRef.current.tx - mouseRef.current.x) * 0.06;
      mouseRef.current.y += (mouseRef.current.ty - mouseRef.current.y) * 0.06;

      ctx!.clearRect(0, 0, width, height);

      // Stars
      const stars = starsRef.current;
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        s.twinkle += dt * 0.001 * s.twinkleSpeed;
        const flick = reducedMotion.current ? 1 : 0.65 + 0.35 * Math.sin(s.twinkle);
        const alpha = Math.min(1, s.baseAlpha * flick);

        const px = s.x + mouseRef.current.x * (s.z * 14);
        const py = s.y + mouseRef.current.y * (s.z * 14);

        ctx!.beginPath();
        ctx!.arc(px, py, s.r, 0, Math.PI * 2);
        const sat = s.hue > 100 ? 30 : 80;
        ctx!.fillStyle = `hsla(${s.hue}, ${sat}%, ${85 + s.z * 10}%, ${alpha})`;
        ctx!.fill();

        // Halo for the brighter near stars
        if (s.z > 0.7) {
          ctx!.beginPath();
          ctx!.arc(px, py, s.r * 3.2, 0, Math.PI * 2);
          const grad = ctx!.createRadialGradient(px, py, 0, px, py, s.r * 3.2);
          grad.addColorStop(0, `hsla(${s.hue}, ${sat}%, 90%, ${alpha * 0.35})`);
          grad.addColorStop(1, `hsla(${s.hue}, ${sat}%, 90%, 0)`);
          ctx!.fillStyle = grad;
          ctx!.fill();
        }
      }

      // Shooting stars
      if (!reducedMotion.current) {
        if (t - lastShooterRef.current > SHOOTER_INTERVAL) {
          lastShooterRef.current = t;
          if (Math.random() < SHOOTER_CHANCE) spawnShooter();
        }
        const shooters = shootersRef.current;
        for (let i = shooters.length - 1; i >= 0; i--) {
          const sh = shooters[i];
          sh.life += 1;
          sh.x += sh.vx;
          sh.y += sh.vy;
          const lifeT = sh.life / sh.maxLife;
          const fade = lifeT < 0.2 ? lifeT / 0.2 : 1 - (lifeT - 0.2) / 0.8;

          const tailLen = 90;
          const tailX = sh.x - sh.vx * (tailLen / Math.hypot(sh.vx, sh.vy));
          const tailY = sh.y - sh.vy * (tailLen / Math.hypot(sh.vx, sh.vy));

          const grad = ctx!.createLinearGradient(sh.x, sh.y, tailX, tailY);
          grad.addColorStop(0, `rgba(174, 245, 248, ${0.95 * fade})`);
          grad.addColorStop(0.4, `rgba(127, 209, 211, ${0.55 * fade})`);
          grad.addColorStop(1, `rgba(127, 209, 211, 0)`);
          ctx!.strokeStyle = grad;
          ctx!.lineWidth = 1.4;
          ctx!.lineCap = "round";
          ctx!.beginPath();
          ctx!.moveTo(sh.x, sh.y);
          ctx!.lineTo(tailX, tailY);
          ctx!.stroke();

          // Bright head dot
          ctx!.beginPath();
          ctx!.arc(sh.x, sh.y, 1.6, 0, Math.PI * 2);
          ctx!.fillStyle = `rgba(255, 255, 255, ${fade})`;
          ctx!.fill();

          if (sh.life >= sh.maxLife || sh.x > width + 50 || sh.y > height + 50) {
            shooters.splice(i, 1);
          }
        }
      }

      rafRef.current = requestAnimationFrame(frame);
    }

    function onMouseMove(e: MouseEvent) {
      // -1..1 normalised, multiplied by small constant in render
      mouseRef.current.tx = (e.clientX / width - 0.5) * -1;
      mouseRef.current.ty = (e.clientY / height - 0.5) * -1;
    }

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMouseMove, { passive: true });
    rafRef.current = requestAnimationFrame(frame);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouseMove);
      mq.removeEventListener("change", onMq);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      style={{
        position: "fixed",
        inset: 0,
        width: "100%",
        height: "100%",
        zIndex: 0,
        pointerEvents: "none",
      }}
    />
  );
}
