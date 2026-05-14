import { useEffect, useRef } from "react";

// Mission-control circuit/data-flow background.
// - Snaps a sparse grid of "nodes" to a soft grid layout
// - Connects nearby nodes with orthogonal (right-angle) "traces"
// - Sends bright "data packets" travelling along the traces
// - Nodes pulse and occasionally emit a radial broadcast ping
// - Mouse parallax on the whole scene for subtle 3D depth
//
// Reads as: "an AI system at work, signals flowing." Clean, sparse,
// mission-control — not a literal factory.

type Node = {
  x: number;
  y: number;
  baseX: number;
  baseY: number;
  brightness: number;          // 0..1 — how bright this node currently is
  baseBrightness: number;      // 0..1 — its resting brightness
  pulsePhase: number;
  pulseSpeed: number;
  hue: number;
  isHub: boolean;              // hubs are larger and broadcast pings
};

type Trace = {
  a: number;                   // node index
  b: number;
  // Pre-computed orthogonal path from a→b: a sequence of (x,y) points
  path: { x: number; y: number; len: number }[];
  totalLen: number;
};

type Packet = {
  trace: number;
  t: number;                   // 0..1 progress along the trace
  speed: number;               // progress per ms
  hue: number;
  size: number;
};

type Ping = {
  x: number;
  y: number;
  age: number;
  maxAge: number;
  hue: number;
};

const GRID_CELL = 110;          // base grid cell in px
const GRID_JITTER = 26;         // how much each node can drift from its grid slot
const HUB_RATIO = 0.10;         // ~10% of nodes are hubs
const MAX_TRACES = 90;
const PACKET_SPAWN_MS = 280;    // try to spawn a packet this often
const PACKET_CHANCE = 0.85;
const MAX_PACKETS = 28;
const PING_INTERVAL_MS = 4500;
const PING_CHANCE = 0.7;
const CONNECT_DIST = GRID_CELL * 1.7;

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

export function CircuitField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | undefined>(undefined);
  const nodesRef = useRef<Node[]>([]);
  const tracesRef = useRef<Trace[]>([]);
  const packetsRef = useRef<Packet[]>([]);
  const pingsRef = useRef<Ping[]>([]);
  const mouseRef = useRef({ tx: 0, ty: 0, x: 0, y: 0 });
  const lastPacketRef = useRef(0);
  const lastPingRef = useRef(0);
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
      const isMobile = window.innerWidth < 700;
      const cell = isMobile ? GRID_CELL * 1.25 : GRID_CELL;
      const cols = Math.ceil(width / cell) + 1;
      const rows = Math.ceil(height / cell) + 1;

      // Place nodes at jittered grid intersections, but skip cells randomly
      // to keep things sparse and unpredictable.
      const nodes: Node[] = [];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          if (Math.random() > 0.62) continue;
          const baseX = c * cell + (Math.random() - 0.5) * GRID_JITTER;
          const baseY = r * cell + (Math.random() - 0.5) * GRID_JITTER;
          const isHub = Math.random() < HUB_RATIO;
          nodes.push({
            x: baseX,
            y: baseY,
            baseX,
            baseY,
            brightness: 0,
            baseBrightness: rand(0.18, 0.55) * (isHub ? 1.4 : 1),
            pulsePhase: Math.random() * Math.PI * 2,
            pulseSpeed: rand(0.4, 1.2),
            hue: Math.random() < 0.85 ? rand(190, 210) : rand(40, 55),
            isHub,
          });
        }
      }
      nodesRef.current = nodes;

      // Build traces — connect each node to up to 2 nearby nodes, prefer
      // orthogonal alignment. Deduplicate.
      const traces: Trace[] = [];
      const seen = new Set<string>();
      for (let i = 0; i < nodes.length && traces.length < MAX_TRACES; i++) {
        const a = nodes[i];
        // Find candidates — close enough, prefer roughly axis-aligned
        const candidates: { idx: number; d: number; align: number }[] = [];
        for (let j = 0; j < nodes.length; j++) {
          if (i === j) continue;
          const b = nodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const d = Math.hypot(dx, dy);
          if (d > CONNECT_DIST || d < cell * 0.6) continue;
          // Alignment score — 1 for perfectly axis-aligned, 0 for 45deg
          const align = Math.max(Math.abs(dx), Math.abs(dy)) / (Math.abs(dx) + Math.abs(dy) || 1);
          candidates.push({ idx: j, d, align });
        }
        candidates.sort((p, q) => q.align - p.align || p.d - q.d);
        const linksToMake = Math.min(2, candidates.length);
        for (let k = 0; k < linksToMake; k++) {
          const j = candidates[k].idx;
          const key = i < j ? `${i}-${j}` : `${j}-${i}`;
          if (seen.has(key)) continue;
          seen.add(key);
          // Build orthogonal path from a→b: go horizontal then vertical
          // (or vice versa, picked randomly so the network looks varied)
          const b = nodes[j];
          const horizFirst = Math.random() < 0.5;
          const corner = horizFirst
            ? { x: b.x, y: a.y }
            : { x: a.x, y: b.y };
          const seg1 = Math.hypot(corner.x - a.x, corner.y - a.y);
          const seg2 = Math.hypot(b.x - corner.x, b.y - corner.y);
          const totalLen = seg1 + seg2;
          if (totalLen < 1) continue;
          traces.push({
            a: i,
            b: j,
            path: [
              { x: a.x, y: a.y, len: 0 },
              { x: corner.x, y: corner.y, len: seg1 },
              { x: b.x, y: b.y, len: totalLen },
            ],
            totalLen,
          });
          if (traces.length >= MAX_TRACES) break;
        }
      }
      tracesRef.current = traces;
      packetsRef.current = [];
      pingsRef.current = [];
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

    function pointAt(trace: Trace, t: number) {
      // Walk the path until we hit the position
      const target = t * trace.totalLen;
      for (let i = 1; i < trace.path.length; i++) {
        const seg = trace.path[i];
        const prev = trace.path[i - 1];
        if (target <= seg.len) {
          const segStart = prev.len;
          const segLen = seg.len - segStart;
          const k = segLen > 0 ? (target - segStart) / segLen : 0;
          return {
            x: prev.x + (seg.x - prev.x) * k,
            y: prev.y + (seg.y - prev.y) * k,
          };
        }
      }
      return { x: trace.path[trace.path.length - 1].x, y: trace.path[trace.path.length - 1].y };
    }

    function spawnPacket() {
      if (packetsRef.current.length >= MAX_PACKETS) return;
      const traces = tracesRef.current;
      if (!traces.length) return;
      const idx = Math.floor(Math.random() * traces.length);
      packetsRef.current.push({
        trace: idx,
        t: 0,
        speed: rand(0.0006, 0.0014),  // progress per ms
        hue: Math.random() < 0.85 ? 195 : 45,
        size: rand(1.6, 2.6),
      });
    }

    function spawnPing() {
      const hubs = nodesRef.current.filter((n) => n.isHub);
      if (!hubs.length) return;
      const n = hubs[Math.floor(Math.random() * hubs.length)];
      pingsRef.current.push({
        x: n.x,
        y: n.y,
        age: 0,
        maxAge: 1600,
        hue: n.hue,
      });
    }

    let last = performance.now();
    function frame(t: number) {
      const dt = Math.min(50, t - last);
      last = t;

      // Smooth mouse parallax
      mouseRef.current.x += (mouseRef.current.tx - mouseRef.current.x) * 0.04;
      mouseRef.current.y += (mouseRef.current.ty - mouseRef.current.y) * 0.04;

      ctx!.clearRect(0, 0, width, height);

      const nodes = nodesRef.current;
      const traces = tracesRef.current;
      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;

      // Update node pulses
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        n.pulsePhase += dt * 0.001 * n.pulseSpeed;
        const flick = reducedMotion.current ? 1 : 0.55 + 0.45 * Math.sin(n.pulsePhase);
        n.brightness = n.baseBrightness * flick;
      }

      // ─── Draw traces ──────────────────────────────────────────────
      for (let i = 0; i < traces.length; i++) {
        const tr = traces[i];
        const a = nodes[tr.a];
        const b = nodes[tr.b];
        if (!a || !b) continue;
        const path = tr.path;
        ctx!.lineCap = "round";
        ctx!.strokeStyle = `rgba(127, 209, 211, ${0.10 + (a.brightness + b.brightness) * 0.06})`;
        ctx!.lineWidth = 0.6;
        ctx!.beginPath();
        ctx!.moveTo(path[0].x + mx * 6, path[0].y + my * 6);
        for (let k = 1; k < path.length; k++) {
          ctx!.lineTo(path[k].x + mx * 6, path[k].y + my * 6);
        }
        ctx!.stroke();
      }

      // ─── Draw nodes ───────────────────────────────────────────────
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        const px = n.x + mx * 8;
        const py = n.y + my * 8;
        const r = n.isHub ? 2.6 : 1.4;
        // halo for hubs
        if (n.isHub) {
          const grad = ctx!.createRadialGradient(px, py, 0, px, py, r * 6);
          grad.addColorStop(0, `hsla(${n.hue}, 70%, 80%, ${n.brightness * 0.35})`);
          grad.addColorStop(1, `hsla(${n.hue}, 70%, 80%, 0)`);
          ctx!.fillStyle = grad;
          ctx!.beginPath();
          ctx!.arc(px, py, r * 6, 0, Math.PI * 2);
          ctx!.fill();
        }
        ctx!.fillStyle = `hsla(${n.hue}, 70%, 78%, ${Math.min(1, n.brightness + 0.25)})`;
        ctx!.beginPath();
        ctx!.arc(px, py, r, 0, Math.PI * 2);
        ctx!.fill();
        // tiny crosshair on hubs
        if (n.isHub) {
          ctx!.strokeStyle = `hsla(${n.hue}, 60%, 75%, ${n.brightness * 0.55})`;
          ctx!.lineWidth = 0.5;
          const cl = 6;
          ctx!.beginPath();
          ctx!.moveTo(px - cl, py); ctx!.lineTo(px - r - 1.2, py);
          ctx!.moveTo(px + r + 1.2, py); ctx!.lineTo(px + cl, py);
          ctx!.moveTo(px, py - cl); ctx!.lineTo(px, py - r - 1.2);
          ctx!.moveTo(px, py + r + 1.2); ctx!.lineTo(px, py + cl);
          ctx!.stroke();
        }
      }

      // ─── Spawn + advance packets ──────────────────────────────────
      if (!reducedMotion.current) {
        if (t - lastPacketRef.current > PACKET_SPAWN_MS) {
          lastPacketRef.current = t;
          if (Math.random() < PACKET_CHANCE) spawnPacket();
        }
        const packets = packetsRef.current;
        for (let i = packets.length - 1; i >= 0; i--) {
          const p = packets[i];
          p.t += p.speed * dt;
          if (p.t >= 1 || !traces[p.trace]) {
            packets.splice(i, 1);
            continue;
          }
          const tr = traces[p.trace];
          const pos = pointAt(tr, p.t);
          const px = pos.x + mx * 6;
          const py = pos.y + my * 6;

          // Trail behind
          const trailT = Math.max(0, p.t - 0.06);
          const trail = pointAt(tr, trailT);
          const tx = trail.x + mx * 6;
          const ty = trail.y + my * 6;
          const grad = ctx!.createLinearGradient(px, py, tx, ty);
          const baseColor = p.hue === 195 ? "127, 209, 211" : "255, 192, 0";
          grad.addColorStop(0, `rgba(${baseColor}, 0.85)`);
          grad.addColorStop(1, `rgba(${baseColor}, 0)`);
          ctx!.strokeStyle = grad;
          ctx!.lineWidth = 1.4;
          ctx!.lineCap = "round";
          ctx!.beginPath();
          ctx!.moveTo(px, py);
          ctx!.lineTo(tx, ty);
          ctx!.stroke();

          // Bright head
          ctx!.fillStyle = p.hue === 195 ? "rgba(174, 245, 248, 0.95)" : "rgba(255, 226, 130, 0.95)";
          ctx!.beginPath();
          ctx!.arc(px, py, p.size, 0, Math.PI * 2);
          ctx!.fill();
        }
      }

      // ─── Spawn + render pings ─────────────────────────────────────
      if (!reducedMotion.current) {
        if (t - lastPingRef.current > PING_INTERVAL_MS) {
          lastPingRef.current = t;
          if (Math.random() < PING_CHANCE) spawnPing();
        }
        const pings = pingsRef.current;
        for (let i = pings.length - 1; i >= 0; i--) {
          const p = pings[i];
          p.age += dt;
          const k = p.age / p.maxAge;
          if (k >= 1) { pings.splice(i, 1); continue; }
          const px = p.x + mx * 8;
          const py = p.y + my * 8;
          const radius = k * 80;
          const alpha = (1 - k) * 0.45;
          ctx!.strokeStyle = `hsla(${p.hue}, 70%, 78%, ${alpha})`;
          ctx!.lineWidth = 1;
          ctx!.beginPath();
          ctx!.arc(px, py, radius, 0, Math.PI * 2);
          ctx!.stroke();
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
