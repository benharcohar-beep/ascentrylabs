import { Canvas, useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";

// A "neural" core — outer wireframe shell whose vertices ripple via 3D
// simplex-style noise, breathes with a multi-harmonic scale pulse, and
// rotates with asymmetric multi-axis frequencies. Reads as alive /
// brain-like rather than as a constant spin.
//
// Geometry is built once (high-subdivision icosahedron); each frame we
// displace vertex positions away from the original positions by a noise
// field anchored on time + the original direction, so the ripple feels
// organic and continuous.

// Tiny pseudo-noise (cheap deterministic value-noise variant)
function noise3(x: number, y: number, z: number) {
  // Sum of three offset sines — fast, surprisingly organic for vertex jitter
  return (
    Math.sin(x * 1.3 + Math.cos(y * 0.7 + z * 0.5) * 1.4) *
      Math.cos(y * 0.9 + z * 1.1) *
      Math.sin(z * 1.7 + x * 0.3) *
      0.5
  );
}

function Core() {
  const groupRef = useRef<THREE.Group>(null);
  const outerMeshRef = useRef<THREE.Mesh>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const targetRot = useRef({ x: 0, y: 0 });
  const t = useRef(0);

  // Build the outer geometry once and keep a copy of its rest-pose vertices
  const outerGeo = useMemo(() => {
    return new THREE.IcosahedronGeometry(1.5, 4);
  }, []);
  const outerRest = useMemo(() => {
    const arr = outerGeo.attributes.position.array as Float32Array;
    return Float32Array.from(arr); // immutable copy
  }, [outerGeo]);

  useFrame((state, dt) => {
    t.current += dt;
    const time = t.current;

    // ─── Vertex ripple ───────────────────────────────────────────────
    // Walk every vertex, push it outward along its original radial
    // direction by a small noise-driven amount that drifts over time.
    const pos = outerGeo.attributes.position.array as Float32Array;
    const rest = outerRest;
    const amp = 0.07; // displacement amplitude (small — readable as breathing)
    for (let i = 0; i < pos.length; i += 3) {
      const x = rest[i];
      const y = rest[i + 1];
      const z = rest[i + 2];
      const n = noise3(x * 1.2 + time * 0.55, y * 1.2 + time * 0.4, z * 1.2 + time * 0.6);
      const len = Math.hypot(x, y, z) || 1;
      const push = 1 + n * amp;
      pos[i] = (x / len) * len * push;
      pos[i + 1] = (y / len) * len * push;
      pos[i + 2] = (z / len) * len * push;
    }
    outerGeo.attributes.position.needsUpdate = true;
    // Note: we deliberately skip computeVertexNormals — the wireframe
    // material doesn't use them, and they're expensive every frame.

    // Mouse-driven target rotation — gentle
    const m = state.mouse;
    targetRot.current.x = m.y * 0.3;
    targetRot.current.y = m.x * 0.45;

    if (groupRef.current) {
      const g = groupRef.current;
      g.rotation.x += (targetRot.current.x - g.rotation.x) * 0.03;
      g.rotation.y += (targetRot.current.y - g.rotation.y) * 0.03;
      // Asymmetric autonomous rotation — irrational frequencies so it never
      // repeats or feels mechanical
      g.rotation.y += dt * 0.10;
      g.rotation.x += dt * 0.034;
      g.rotation.z = Math.sin(time * 0.21) * 0.06;

      // Multi-harmonic breathing pulse on the entire group
      const breath = 1 + Math.sin(time * 0.85) * 0.04 + Math.sin(time * 1.7) * 0.015;
      g.scale.setScalar(breath);
    }

    if (innerRef.current) {
      innerRef.current.rotation.x -= dt * 0.5;
      innerRef.current.rotation.z += dt * 0.38;
      innerRef.current.rotation.y += dt * 0.22;
      const innerPulse = 1 + Math.sin(time * 0.85 + Math.PI) * 0.08;
      innerRef.current.scale.setScalar(innerPulse);
    }

    if (glowRef.current) {
      const glow = 0.95 + Math.sin(time * 1.2) * 0.07;
      glowRef.current.scale.setScalar(glow);
    }
  });

  const ringPositions = useMemo(() => {
    const N = 260;
    const arr = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const phi = Math.acos(1 - (2 * (i + 0.5)) / N);
      const theta = Math.PI * (1 + Math.sqrt(5)) * i;
      const r = 1.95;
      arr[i * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = r * Math.cos(phi);
    }
    return arr;
  }, []);

  return (
    <group ref={groupRef}>
      {/* Outer rippling shell — primary brain effect. Geometry mutated each frame. */}
      <mesh ref={outerMeshRef} geometry={outerGeo}>
        <meshBasicMaterial color="#7fd1d3" wireframe transparent opacity={0.78} />
      </mesh>

      {/* Faint outer halo shell */}
      <mesh scale={1.18}>
        <icosahedronGeometry args={[1.5, 1]} />
        <meshBasicMaterial color="#5b9dd9" wireframe transparent opacity={0.16} />
      </mesh>

      {/* Inner counter-rotating geometry — gold */}
      <mesh ref={innerRef}>
        <octahedronGeometry args={[0.55, 0]} />
        <meshBasicMaterial color="#ffc000" wireframe transparent opacity={0.85} />
      </mesh>

      {/* Glowing core sphere */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.28, 32, 32]} />
        <meshBasicMaterial color="#aef5f8" transparent opacity={0.9} />
      </mesh>

      {/* Sparse particle shell */}
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[ringPositions, 3]} />
        </bufferGeometry>
        <pointsMaterial
          size={0.025}
          color="#aef5f8"
          transparent
          opacity={0.65}
          sizeAttenuation
        />
      </points>
    </group>
  );
}

function Lights() {
  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[3, 3, 5]} intensity={1.4} color="#7fd1d3" />
      <pointLight position={[-3, -2, -3]} intensity={0.7} color="#ffc000" />
    </>
  );
}

export function WireframeCore() {
  return (
    <div className="wireframe-core">
      <Canvas
        camera={{ position: [0, 0, 5], fov: 45 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        dpr={[1, 2]}
      >
        <Lights />
        <Core />
      </Canvas>
      <div className="wireframe-halo" aria-hidden />
    </div>
  );
}
