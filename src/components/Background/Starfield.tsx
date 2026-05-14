import { useEffect, useRef } from "react";

type Star = {
  x: number;
  y: number;
  z: number;
  r: number;
  baseAlpha: number;
  twinkle: number;
  twinkleSpeed: number;
  hue: number;
  bright: boolean;
};

type Shooter = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  hue: number;
};

type Comet = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  size: number;
};

type Constellation = {
  a: number; // index of star a
  b: number; // index of star b
  alpha: number;
};

const STAR_COUNT = 620;            // ~2x denser than v1
const SHOOTER_INTERVAL = 4500;     // ms between attempts (was 9000)
const SHOOTER_CHANCE = 0.78;       // probability per attempt (was 0.55)
const COMET_INTERVAL = 18000;      // slow drifting comets less frequent
const COMET_CHANCE = 0.55;
const CONSTELLATION_LINK_DIST = 110; // px — bright stars within this become linked
const MAX_CONSTELLATION_LINES = 22;

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

export function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | undefined>(undefined);
  const starsRef = useRef<Star[]>([]);
  const shootersRef = useRef<Shooter[]>([]);
  const cometsRef = useRef<Comet[]>([]);
  const constellationsRef = useRef<Constellation[]>([]);
  const mouseRef = useRef({ x: 0, y: 0, tx: 0, ty: 0 });
  const lastShooterRef = useRef(0);
  const lastCometRef = useRef(0);
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
      const isMobile = window.innerWidth < 700;
      const count = isMobile ? Math.floor(STAR_COUNT * 0.5) : STAR_COUNT;
      for (let i = 0; i < count; i++) {
        const z = Math.pow(Math.random(), 1.6);
        const bright = Math.random() < 0.08;            // ~8% bright "anchor" stars
        stars.push({
          x: Math.random() * width,
          y: Math.random() * height,
          z,
          r: rand(0.3, 1.6) * (0.6 + z * 1.4) * (bright ? 1.6 : 1),
          baseAlpha: rand(0.35, 1.0) * (0.4 + z * 0.6),
          twinkle: Math.random() * Math.PI * 2,
          twinkleSpeed: rand(0.4, 1.6),
          // Mostly cool blue-white, occasionally golden, rarely orange-red
          hue: Math.random() < 0.78
            ? rand(195, 220)
            : Math.random() < 0.85
              ? rand(35, 55)
              : rand(8, 22),
          bright,
        });
      }
      starsRef.current = stars;

      // Build constellation links between nearby bright stars
      const brightIdx = stars.map((s, i) => (s.bright ? i : -1)).filter((i) => i >= 0);
      const links: Constellation[] = [];
      for (let i = 0; i < brightIdx.length && links.length < MAX_CONSTELLATION_LINES; i++) {
        for (let j = i + 1; j < brightIdx.length && links.length < MAX_CONSTELLATION_LINES; j++) {
          const a = stars[brightIdx[i]];
          const b = stars[brightIdx[j]];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < CONSTELLATION_LINK_DIST) {
            links.push({ a: brightIdx[i], b: brightIdx[j], alpha: 1 - d / CONSTELLATION_LINK_DIST });
          }
        }
      }
      constellationsRef.current = links;
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
      const fromTop = Math.random() < 0.5;
      const x = fromTop ? rand(-50, width * 0.4) : -50;
      const y = fromTop ? -50 : rand(0, height * 0.6);
      const angle = rand(Math.PI * 0.18, Math.PI * 0.32);
      const speed = rand(8, 16);
      shootersRef.current.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 0,
        maxLife: rand(60, 130),
        hue: Math.random() < 0.85 ? 200 : 45, // mostly cyan, occasionally gold
      });
    }

    function spawnComet() {
      // Slow, persistent diagonal drifter with a long fading tail
      const fromLeft = Math.random() < 0.5;
      const x = fromLeft ? -100 : width + 100;
      const y = rand(height * 0.1, height * 0.7);
      const speed = rand(0.6, 1.2); // SLOW
      const angle = rand(Math.PI * 0.05, Math.PI * 0.18) * (fromLeft ? 1 : -1);
      cometsRef.current.push({
        x,
        y,
        vx: (fromLeft ? Math.cos(angle) : -Math.cos(angle)) * speed,
        vy: Math.sin(Math.abs(angle)) * speed,
        life: 0,
        maxLife: 9999,
        size: rand(1.4, 2.4),
      });
    }

    let last = performance.now();
    function frame(t: number) {
      const dt = Math.min(50, t - last);
      last = t;

      mouseRef.current.x += (mouseRef.current.tx - mouseRef.current.x) * 0.06;
      mouseRef.current.y += (mouseRef.current.ty - mouseRef.current.y) * 0.06;

      ctx!.clearRect(0, 0, width, height);

      const stars = starsRef.current;

      // ── Constellation lines (drawn first so stars sit on top) ──
      const links = constellationsRef.current;
      ctx!.lineCap = "round";
      for (let i = 0; i < links.length; i++) {
        const a = stars[links[i].a];
        const b = stars[links[i].b];
        if (!a || !b) continue;
        const ax = a.x + mouseRef.current.x * (a.z * 14);
        const ay = a.y + mouseRef.current.y * (a.z * 14);
        const bx = b.x + mouseRef.current.x * (b.z * 14);
        const by = b.y + mouseRef.current.y * (b.z * 14);
        // Slow shimmer on each line
        const shimmer = 0.6 + 0.4 * Math.sin(t * 0.0008 + i);
        ctx!.strokeStyle = `rgba(127, 209, 211, ${links[i].alpha * 0.10 * shimmer})`;
        ctx!.lineWidth = 0.7;
        ctx!.beginPath();
        ctx!.moveTo(ax, ay);
        ctx!.lineTo(bx, by);
        ctx!.stroke();
      }

      // ── Stars ──
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        s.twinkle += dt * 0.001 * s.twinkleSpeed;
        const flick = reducedMotion.current ? 1 : 0.55 + 0.45 * Math.sin(s.twinkle);
        const alpha = Math.min(1, s.baseAlpha * flick);

        const px = s.x + mouseRef.current.x * (s.z * 14);
        const py = s.y + mouseRef.current.y * (s.z * 14);

        ctx!.beginPath();
        ctx!.arc(px, py, s.r, 0, Math.PI * 2);
        const sat = s.hue > 100 && s.hue < 230 ? 35 : 80;
        ctx!.fillStyle = `hsla(${s.hue}, ${sat}%, ${85 + s.z * 10}%, ${alpha})`;
        ctx!.fill();

        // Halo on bright + near stars
        if (s.bright || s.z > 0.7) {
          const haloR = s.bright ? s.r * 4.5 : s.r * 3.2;
          const grad = ctx!.createRadialGradient(px, py, 0, px, py, haloR);
          const haloAlpha = (s.bright ? 0.5 : 0.32) * alpha;
          grad.addColorStop(0, `hsla(${s.hue}, ${sat}%, 92%, ${haloAlpha})`);
          grad.addColorStop(1, `hsla(${s.hue}, ${sat}%, 92%, 0)`);
          ctx!.beginPath();
          ctx!.arc(px, py, haloR, 0, Math.PI * 2);
          ctx!.fillStyle = grad;
          ctx!.fill();

          // Cross-glint on the brightest stars, when they're near the peak of their twinkle
          if (s.bright && flick > 0.95) {
            ctx!.strokeStyle = `hsla(${s.hue}, ${sat}%, 95%, ${alpha * 0.45})`;
            ctx!.lineWidth = 0.6;
            const len = s.r * 8;
            ctx!.beginPath();
            ctx!.moveTo(px - len, py); ctx!.lineTo(px + len, py);
            ctx!.moveTo(px, py - len); ctx!.lineTo(px, py + len);
            ctx!.stroke();
          }
        }
      }

      // ── Comets (slow + persistent, drawn before shooting stars) ──
      if (!reducedMotion.current) {
        if (t - lastCometRef.current > COMET_INTERVAL) {
          lastCometRef.current = t;
          if (Math.random() < COMET_CHANCE) spawnComet();
        }
        const comets = cometsRef.current;
        for (let i = comets.length - 1; i >= 0; i--) {
          const c = comets[i];
          c.x += c.vx;
          c.y += c.vy;
          c.life += dt;
          // Long fading tail
          const tailLen = 220;
          const dirLen = Math.hypot(c.vx, c.vy) || 1;
          const tx = c.x - (c.vx / dirLen) * tailLen;
          const ty = c.y - (c.vy / dirLen) * tailLen;
          const grad = ctx!.createLinearGradient(c.x, c.y, tx, ty);
          grad.addColorStop(0, `rgba(255, 240, 200, 0.7)`);
          grad.addColorStop(0.3, `rgba(174, 245, 248, 0.32)`);
          grad.addColorStop(1, `rgba(127, 209, 211, 0)`);
          ctx!.strokeStyle = grad;
          ctx!.lineWidth = 1.1;
          ctx!.beginPath();
          ctx!.moveTo(c.x, c.y);
          ctx!.lineTo(tx, ty);
          ctx!.stroke();
          // Bright head
          ctx!.beginPath();
          ctx!.arc(c.x, c.y, c.size, 0, Math.PI * 2);
          ctx!.fillStyle = "rgba(255, 250, 230, 0.95)";
          ctx!.fill();
          if (c.x < -250 || c.x > width + 250 || c.y < -250 || c.y > height + 250) {
            comets.splice(i, 1);
          }
        }
      }

      // ── Shooting stars (fast streaks) ──
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

          const tailLen = 110;
          const dirLen = Math.hypot(sh.vx, sh.vy) || 1;
          const tailX = sh.x - (sh.vx / dirLen) * tailLen;
          const tailY = sh.y - (sh.vy / dirLen) * tailLen;
          const headColor = sh.hue === 200 ? "174, 245, 248" : "255, 226, 130";
          const tailColor = sh.hue === 200 ? "127, 209, 211" : "255, 192, 0";
          const grad = ctx!.createLinearGradient(sh.x, sh.y, tailX, tailY);
          grad.addColorStop(0, `rgba(${headColor}, ${0.95 * fade})`);
          grad.addColorStop(0.4, `rgba(${tailColor}, ${0.55 * fade})`);
          grad.addColorStop(1, `rgba(${tailColor}, 0)`);
          ctx!.strokeStyle = grad;
          ctx!.lineWidth = 1.5;
          ctx!.beginPath();
          ctx!.moveTo(sh.x, sh.y);
          ctx!.lineTo(tailX, tailY);
          ctx!.stroke();

          ctx!.beginPath();
          ctx!.arc(sh.x, sh.y, 1.7, 0, Math.PI * 2);
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
