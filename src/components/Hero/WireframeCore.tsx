import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useRef, useMemo } from "react";
import * as THREE from "three";

// Scroll progress - shared ref read by the R3F useFrame loop. We avoid
// React state so the scroll-driven transforms don't trigger re-renders.
const scrollProgressRef = { current: 0 };

function useHeroScrollProgress() {
  useEffect(() => {
    const onScroll = () => {
      // Track how far the user has scrolled out of the hero. Once the
      // viewport top has scrolled past the bottom of the hero, progress
      // hits 1 and stops driving transforms.
      const hero = document.getElementById("top");
      if (!hero) return;
      const rect = hero.getBoundingClientRect();
      const total = rect.height;
      // -rect.top represents how much of the hero has scrolled past the top
      const scrolledPast = Math.max(0, -rect.top);
      scrollProgressRef.current = Math.min(1, scrolledPast / Math.max(1, total));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);
}

// Mission-control orrery: three orthogonal wireframe rings rotating at
// independent speeds, an inner geometric "core" doing slow counter-rotation,
// a bright glowing center, and "data beads" orbiting along each ring at
// their own pace. Reads as a holographic AI control hub - clean, technical,
// in motion. Mouse parallax on the whole assembly.
//
// HTML overlay (in the parent .wireframe-core) adds corner brackets +
// crosshair markers + a small mono-text status readout for the HUD feel.

function Orrery() {
  const groupRef = useRef<THREE.Group>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const ring1Ref = useRef<THREE.Group>(null);
  const ring2Ref = useRef<THREE.Group>(null);
  const ring3Ref = useRef<THREE.Group>(null);
  const beads1Ref = useRef<THREE.Points>(null);
  const beads2Ref = useRef<THREE.Points>(null);
  const beads3Ref = useRef<THREE.Points>(null);
  const targetRot = useRef({ x: 0, y: 0 });
  const t = useRef(0);

  // Generate bead positions evenly-spaced around a unit ring (in XY plane);
  // each ring's <group> tilts the whole thing into its target orientation.
  const beadPositions = useMemo(() => {
    const N = 6;
    const arr = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const theta = (i / N) * Math.PI * 2;
      arr[i * 3 + 0] = Math.cos(theta);
      arr[i * 3 + 1] = Math.sin(theta);
      arr[i * 3 + 2] = 0;
    }
    return arr;
  }, []);

  useFrame((state, dt) => {
    t.current += dt;
    const time = t.current;
    const sp = scrollProgressRef.current;  // 0..1 across the hero
    // Scroll-driven boosts: rotation accelerates, rings spread, core grows
    const rotBoost = 1 + sp * 4;            // 1× → 5× rotation speed
    const ringSpread = sp * 0.6;            // tilts rings outward
    const innerGrow = 1 + sp * 0.9;         // inner core scales up
    const glowGrow = 1 + sp * 1.2;          // bright core scales up

    // Mouse parallax - gentle
    const m = state.mouse;
    targetRot.current.x = m.y * 0.25;
    targetRot.current.y = m.x * 0.4;

    if (groupRef.current) {
      const g = groupRef.current;
      g.rotation.x += (targetRot.current.x - g.rotation.x) * 0.03;
      g.rotation.y += (targetRot.current.y - g.rotation.y) * 0.03;
      g.rotation.y += dt * 0.05 * rotBoost;
      g.rotation.z = Math.sin(time * 0.18) * 0.03;
      // Multi-harmonic breathing - shrinks slightly as we scroll so the
      // expanding inner core has room to grow within the canvas
      const breath = 1 + Math.sin(time * 0.7) * 0.02 + Math.sin(time * 1.5) * 0.008;
      g.scale.setScalar(breath * (1 - sp * 0.15));
    }

    // Each ring rotates around its tilted axis; rotation accelerates with scroll
    if (ring1Ref.current) {
      ring1Ref.current.rotation.z += dt * 0.18 * rotBoost;
      ring1Ref.current.rotation.x = 0.4 + ringSpread;
    }
    if (ring2Ref.current) {
      ring2Ref.current.rotation.z += dt * 0.13 * rotBoost;
      ring2Ref.current.rotation.x = Math.PI / 2 + 0.2 - ringSpread * 0.6;
    }
    if (ring3Ref.current) {
      ring3Ref.current.rotation.z -= dt * 0.10 * rotBoost;
      ring3Ref.current.rotation.x = Math.PI / 4 + ringSpread * 0.5;
    }
    if (beads1Ref.current) beads1Ref.current.rotation.z += dt * 0.32 * rotBoost;
    if (beads2Ref.current) beads2Ref.current.rotation.z += dt * 0.22 * rotBoost;
    if (beads3Ref.current) beads3Ref.current.rotation.z -= dt * 0.27 * rotBoost;

    if (innerRef.current) {
      innerRef.current.rotation.x -= dt * 0.45 * rotBoost;
      innerRef.current.rotation.z += dt * 0.32 * rotBoost;
      innerRef.current.rotation.y += dt * 0.18 * rotBoost;
      const inner = 1 + Math.sin(time * 0.7 + Math.PI) * 0.06;
      innerRef.current.scale.setScalar(inner * innerGrow);
    }

    if (glowRef.current) {
      const glow = 0.95 + Math.sin(time * 1.1) * 0.06;
      glowRef.current.scale.setScalar(glow * glowGrow);
    }
  });

  return (
    <group ref={groupRef}>
      {/* Ring 1 - XY plane (slight tilt) - cyan, primary */}
      <group ref={ring1Ref} rotation={[0.4, 0, 0]}>
        <mesh>
          <torusGeometry args={[1.95, 0.008, 6, 96]} />
          <meshBasicMaterial color="#7fd1d3" wireframe={false} transparent opacity={0.85} />
        </mesh>
        <points ref={beads1Ref}>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[beadPositions, 3]} />
          </bufferGeometry>
          <pointsMaterial size={0.09} color="#aef5f8" transparent opacity={0.95} sizeAttenuation />
        </points>
      </group>

      {/* Ring 2 - XZ plane (perpendicular, tilted other way) - blue */}
      <group ref={ring2Ref} rotation={[Math.PI / 2 + 0.2, 0, 0]}>
        <mesh>
          <torusGeometry args={[1.7, 0.007, 6, 96]} />
          <meshBasicMaterial color="#5b9dd9" transparent opacity={0.7} />
        </mesh>
        <points ref={beads2Ref}>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[beadPositions, 3]} />
          </bufferGeometry>
          <pointsMaterial size={0.07} color="#aef5f8" transparent opacity={0.85} sizeAttenuation />
        </points>
      </group>

      {/* Ring 3 - diagonal - gold accent */}
      <group ref={ring3Ref} rotation={[Math.PI / 4, Math.PI / 4, 0]}>
        <mesh>
          <torusGeometry args={[1.45, 0.006, 6, 96]} />
          <meshBasicMaterial color="#ffc000" transparent opacity={0.6} />
        </mesh>
        <points ref={beads3Ref}>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[beadPositions, 3]} />
          </bufferGeometry>
          <pointsMaterial size={0.07} color="#ffe282" transparent opacity={0.9} sizeAttenuation />
        </points>
      </group>

      {/* Faint outer wireframe shell - gives the orrery something to "contain" */}
      <mesh>
        <icosahedronGeometry args={[2.3, 1]} />
        <meshBasicMaterial color="#5b9dd9" wireframe transparent opacity={0.10} />
      </mesh>

      {/* Inner geometric core - slowly counter-rotating */}
      <mesh ref={innerRef}>
        <icosahedronGeometry args={[0.55, 1]} />
        <meshBasicMaterial color="#7fd1d3" wireframe transparent opacity={0.7} />
      </mesh>

      {/* Bright glowing core */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.3, 32, 32]} />
        <meshBasicMaterial color="#aef5f8" transparent opacity={0.95} />
      </mesh>
    </group>
  );
}

function Lights() {
  return (
    <>
      <ambientLight intensity={0.6} />
      <pointLight position={[3, 3, 5]} intensity={1.4} color="#7fd1d3" />
      <pointLight position={[-3, -2, -3]} intensity={0.7} color="#ffc000" />
    </>
  );
}

export function WireframeCore() {
  useHeroScrollProgress();
  return (
    <div className="wireframe-core">
      <Canvas
        camera={{ position: [0, 0, 5.4], fov: 45 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        dpr={[1, 2]}
      >
        <Lights />
        <Orrery />
      </Canvas>

      {/* HUD overlay - only the soft crosshair grid through the canvas.
          Corner brackets + readouts removed because they collided with the
          orbital nav labels at the same corners. */}
      <div className="hud" aria-hidden>
        <span className="hud-cross hud-cross-h" />
        <span className="hud-cross hud-cross-v" />
      </div>

      <div className="wireframe-halo" aria-hidden />
    </div>
  );
}
