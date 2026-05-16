import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";
import "./factory3d.css";

// 3D wireframe factory floor in WebGL. Lazy-loaded via the same chunk as
// WireframeCore (both depend on three.js + R3F).
//
// Composition: a perspective view across a grid floor with five
// articulated robotic arms running a continuous pick → lift → swing →
// place → return cycle. Each arm has its own scale + phase + hue so the
// floor reads as a busy plant, not a row of clones. A long conveyor
// belt runs the length of the scene with crates traveling on it.
//
// All geometry is procedural (primitives) — small footprint per arm,
// runs comfortably at 60fps. Materials are wireframe + low-opacity
// solids so it matches the rest of the site's blueprint aesthetic.

type ArmConfig = {
  id: string;
  position: [number, number, number];
  scale: number;
  phase: number;          // seconds offset
  cycle: number;          // seconds per full cycle
  baseYaw: number;        // radians — direction the arm faces
  hue: "cyan" | "blue" | "gold";
};

const ARMS: ArmConfig[] = [
  { id: "A1", position: [-7,   0, -1],  scale: 1.0,  phase: 0,    cycle: 9,  baseYaw: -0.2, hue: "cyan" },
  { id: "A2", position: [-3.6, 0,  0.5], scale: 0.9, phase: -2.4, cycle: 8,  baseYaw:  0.1, hue: "blue" },
  { id: "A3", position: [ 0,   0, -0.8], scale: 1.1, phase: -4.6, cycle: 10, baseYaw: -0.05, hue: "cyan" },
  { id: "A4", position: [ 3.6, 0,  0.5], scale: 0.85, phase: -1.1, cycle: 9,  baseYaw:  0.18, hue: "gold" },
  { id: "A5", position: [ 7,   0, -1],  scale: 1.0,  phase: -6,   cycle: 11, baseYaw: -0.15, hue: "cyan" },
];

const HUE_COLOR = {
  cyan: "#7fd1d3",
  blue: "#5b9dd9",
  gold: "#ffc000",
};

// Cycle phases — same beats as the SVG version, but expressed in radians
// for 3D rotations.
type Pose = { baseYaw: number; shoulder: number; elbow: number; wrist: number; grip: number };

function poseFor(t: number, cycle: number, baseYawBias: number): Pose {
  // Normalize 0..1 within the cycle
  const k = ((t % cycle) + cycle) % cycle;
  const p = k / cycle;
  // Piecewise interpolation between keyframes
  const KEYS: { p: number; pose: Pose }[] = [
    { p: 0.00, pose: { baseYaw: baseYawBias,        shoulder: -0.18, elbow:  1.15, wrist:  0.00, grip: 0.55 } },
    { p: 0.18, pose: { baseYaw: baseYawBias,        shoulder:  0.55, elbow:  1.50, wrist: -0.35, grip: 0.55 } },
    { p: 0.28, pose: { baseYaw: baseYawBias,        shoulder:  0.55, elbow:  1.50, wrist: -0.35, grip: 0.05 } },
    { p: 0.42, pose: { baseYaw: baseYawBias,        shoulder:  0.10, elbow:  0.55, wrist: -0.10, grip: 0.05 } },
    { p: 0.58, pose: { baseYaw: baseYawBias + 1.05, shoulder: -0.05, elbow:  0.80, wrist:  0.25, grip: 0.05 } },
    { p: 0.72, pose: { baseYaw: baseYawBias + 1.05, shoulder:  0.40, elbow:  1.30, wrist:  0.25, grip: 0.05 } },
    { p: 0.78, pose: { baseYaw: baseYawBias + 1.05, shoulder:  0.40, elbow:  1.30, wrist:  0.25, grip: 0.55 } },
    { p: 0.92, pose: { baseYaw: baseYawBias,        shoulder: -0.18, elbow:  1.15, wrist:  0.00, grip: 0.55 } },
    { p: 1.00, pose: { baseYaw: baseYawBias,        shoulder: -0.18, elbow:  1.15, wrist:  0.00, grip: 0.55 } },
  ];
  // Find the two keys we're between
  let a = KEYS[0], b = KEYS[1];
  for (let i = 0; i < KEYS.length - 1; i++) {
    if (p >= KEYS[i].p && p <= KEYS[i + 1].p) {
      a = KEYS[i];
      b = KEYS[i + 1];
      break;
    }
  }
  const span = b.p - a.p;
  const local = span > 0 ? (p - a.p) / span : 0;
  // Smooth-step ease so transitions don't feel mechanical
  const e = local * local * (3 - 2 * local);
  return {
    baseYaw:  a.pose.baseYaw  + (b.pose.baseYaw  - a.pose.baseYaw)  * e,
    shoulder: a.pose.shoulder + (b.pose.shoulder - a.pose.shoulder) * e,
    elbow:    a.pose.elbow    + (b.pose.elbow    - a.pose.elbow)    * e,
    wrist:    a.pose.wrist    + (b.pose.wrist    - a.pose.wrist)    * e,
    grip:     a.pose.grip     + (b.pose.grip     - a.pose.grip)     * e,
  };
}

function Arm({ cfg, t0 }: { cfg: ArmConfig; t0: React.MutableRefObject<number> }) {
  const baseRef = useRef<THREE.Group>(null);     // yaw pivot
  const shoulderRef = useRef<THREE.Group>(null); // pitch — at top of base column
  const elbowRef = useRef<THREE.Group>(null);    // pitch — at top of upper arm
  const wristRef = useRef<THREE.Group>(null);    // pitch — at top of forearm
  const fingerLRef = useRef<THREE.Group>(null);  // hinge — at wrist
  const fingerRRef = useRef<THREE.Group>(null);
  const color = HUE_COLOR[cfg.hue];

  useFrame(() => {
    const local = t0.current + cfg.phase;
    const pose = poseFor(local, cfg.cycle, cfg.baseYaw);
    if (baseRef.current) baseRef.current.rotation.y = pose.baseYaw;
    if (shoulderRef.current) shoulderRef.current.rotation.x = pose.shoulder;
    if (elbowRef.current) elbowRef.current.rotation.x = -pose.elbow;
    if (wristRef.current) wristRef.current.rotation.x = pose.wrist;
    if (fingerLRef.current) fingerLRef.current.rotation.x = -pose.grip;
    if (fingerRRef.current) fingerRRef.current.rotation.x =  pose.grip;
  });

  return (
    <group position={cfg.position} scale={cfg.scale}>
      {/* Floor pedestal (static) */}
      <mesh position={[0, 0.06, 0]}>
        <cylinderGeometry args={[0.42, 0.5, 0.12, 16]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.55} />
      </mesh>
      <mesh position={[0, 0.06, 0]}>
        <cylinderGeometry args={[0.42, 0.5, 0.12, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.08} />
      </mesh>

      {/* Base column — rotates in yaw */}
      <group ref={baseRef} position={[0, 0.18, 0]}>
        <mesh position={[0, 0.18, 0]}>
          <cylinderGeometry args={[0.22, 0.28, 0.36, 12]} />
          <meshBasicMaterial color={color} wireframe transparent opacity={0.65} />
        </mesh>
        {/* Shoulder hub */}
        <mesh position={[0, 0.38, 0]}>
          <sphereGeometry args={[0.18, 12, 12]} />
          <meshBasicMaterial color={color} wireframe transparent opacity={0.75} />
        </mesh>

        {/* Shoulder pitch group */}
        <group ref={shoulderRef} position={[0, 0.38, 0]}>
          {/* Upper arm — points up along +Y when shoulder=0 */}
          <mesh position={[0, 0.6, 0]}>
            <boxGeometry args={[0.22, 1.2, 0.22]} />
            <meshBasicMaterial color={color} wireframe transparent opacity={0.7} />
          </mesh>
          <mesh position={[0, 0.6, 0]}>
            <boxGeometry args={[0.22, 1.2, 0.22]} />
            <meshBasicMaterial color={color} transparent opacity={0.08} />
          </mesh>
          {/* Elbow hub */}
          <mesh position={[0, 1.2, 0]}>
            <sphereGeometry args={[0.14, 12, 12]} />
            <meshBasicMaterial color={color} wireframe transparent opacity={0.75} />
          </mesh>

          {/* Elbow pitch group */}
          <group ref={elbowRef} position={[0, 1.2, 0]}>
            {/* Forearm */}
            <mesh position={[0, 0.5, 0]}>
              <boxGeometry args={[0.18, 1.0, 0.18]} />
              <meshBasicMaterial color={color} wireframe transparent opacity={0.7} />
            </mesh>
            <mesh position={[0, 0.5, 0]}>
              <boxGeometry args={[0.18, 1.0, 0.18]} />
              <meshBasicMaterial color={color} transparent opacity={0.08} />
            </mesh>
            {/* Wrist hub */}
            <mesh position={[0, 1.0, 0]}>
              <sphereGeometry args={[0.11, 10, 10]} />
              <meshBasicMaterial color={color} wireframe transparent opacity={0.75} />
            </mesh>

            {/* Wrist pitch group */}
            <group ref={wristRef} position={[0, 1.0, 0]}>
              {/* Gripper hub */}
              <mesh position={[0, 0.14, 0]}>
                <boxGeometry args={[0.22, 0.14, 0.22]} />
                <meshBasicMaterial color={color} wireframe transparent opacity={0.8} />
              </mesh>

              {/* Two fingers, hinging at their base outward */}
              <group ref={fingerLRef} position={[-0.07, 0.22, 0]}>
                <mesh position={[0, 0.12, 0]}>
                  <boxGeometry args={[0.06, 0.24, 0.08]} />
                  <meshBasicMaterial color={color} wireframe transparent opacity={0.85} />
                </mesh>
              </group>
              <group ref={fingerRRef} position={[0.07, 0.22, 0]}>
                <mesh position={[0, 0.12, 0]}>
                  <boxGeometry args={[0.06, 0.24, 0.08]} />
                  <meshBasicMaterial color={color} wireframe transparent opacity={0.85} />
                </mesh>
              </group>
            </group>
          </group>
        </group>
      </group>
    </group>
  );
}

function Conveyor() {
  // Floating crates that travel along an implied belt path. We dropped
  // the solid belt slab because, viewed edge-on at this camera angle, it
  // appeared as a hard horizontal line cutting across the entire scene.
  // The crates themselves still suggest a conveyor in motion without
  // introducing the artifact.
  const cratesRef = useRef<THREE.Group>(null);
  const tRef = useRef(0);
  useFrame((_, dt) => {
    tRef.current += dt;
    if (!cratesRef.current) return;
    cratesRef.current.children.forEach((c, i) => {
      const speed = 0.7;
      const span = 24;
      const x = ((tRef.current * speed + i * 4) % span) - span / 2;
      c.position.x = x;
    });
  });
  return (
    <group position={[0, 0, 2.4]}>
      <group ref={cratesRef}>
        {Array.from({ length: 6 }).map((_, i) => (
          <mesh key={i} position={[0, 0.18, 0]}>
            <boxGeometry args={[0.32, 0.22, 0.28]} />
            <meshBasicMaterial color="#aef5f8" wireframe transparent opacity={0.7} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

// Wireframe floor grid was removed — its near edge (closest to camera)
// was inside the fog-near distance, so it rendered as a sharp horizontal
// line cutting across the lower portion of the viewport. The CSS
// .bg-grid overlay behind the canvas still provides the "floor grid"
// vibe, and the arms have their own pedestal cylinders, so there's
// no visual orphaning.

function Scene() {
  const t0 = useRef(0);
  useFrame((_, dt) => { t0.current += dt; });
  return (
    <>
      <fog attach="fog" args={["#03030a", 8, 26]} />
      <Conveyor />
      {ARMS.map((a) => (
        <Arm key={a.id} cfg={a} t0={t0} />
      ))}
    </>
  );
}

export function RoboticFactory3D() {
  // Camera composition tuned for full-viewport canvas:
  //   - higher y (3.6) so we look down on the factory floor more
  //   - lookAt offset DOWN (the Camera default looks at origin; we shift
  //     the scene visually by raising the arms' rendering position via
  //     a higher camera that tilts down further). Result: arms appear
  //     in the bottom half of the viewport, fully visible, with empty
  //     space above for hero/page content to breathe.
  return (
    <div className="factory3d" aria-hidden>
      <Canvas
        camera={{ position: [0, 3.6, 8.5], fov: 38 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        dpr={[1, 2]}
      >
        <Scene />
      </Canvas>
    </div>
  );
}
