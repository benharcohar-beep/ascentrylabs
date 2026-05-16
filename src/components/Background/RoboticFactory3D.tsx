import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import "./factory3d.css";

// A single central AI processing rig. One substantial wireframe hub in
// the middle of the scene with four articulated arms radiating from it
// at different angles. No conveyor, no orbs — arms do flowing
// articulated motion (scanning / calibrating / sweeping) on their own
// cycles. Whole machine in one accent color so it reads as a single
// unified unit instead of a multi-hue assembly.

const ACCENT = "#7fd1d3";

type ArmConfig = {
  id: string;
  attachYaw: number;       // radians around hub Y
  attachY: number;         // height on hub
  phase: number;           // seconds offset
  cycle: number;           // seconds per cycle
};

const ARMS: ArmConfig[] = [
  { id: "A1", attachYaw: -0.95, attachY: 0.9, phase:  0.0, cycle: 7.5 },
  { id: "A2", attachYaw: -0.32, attachY: 1.4, phase: -1.8, cycle: 8.5 },
  { id: "A3", attachYaw:  0.32, attachY: 1.4, phase: -3.6, cycle: 7.0 },
  { id: "A4", attachYaw:  0.95, attachY: 0.9, phase: -5.0, cycle: 8.0 },
];

type Pose = { shoulder: number; elbow: number; wrist: number };

// Flowing motion — sweep through smooth keyframes. No grip animation
// because there's nothing to pick up. Reads as the machine sweeping,
// scanning, calibrating.
const KEYS = [
  { p: 0.00, pose: { shoulder: -0.10, elbow: 1.20, wrist:  0.25 } },
  { p: 0.25, pose: { shoulder:  0.40, elbow: 1.55, wrist: -0.30 } },
  { p: 0.50, pose: { shoulder:  0.60, elbow: 0.85, wrist:  0.15 } },
  { p: 0.75, pose: { shoulder:  0.20, elbow: 1.40, wrist: -0.25 } },
  { p: 1.00, pose: { shoulder: -0.10, elbow: 1.20, wrist:  0.25 } },
];

function poseFor(t: number, cycle: number): Pose {
  const k = ((t % cycle) + cycle) % cycle;
  const p = k / cycle;
  let a = KEYS[0], b = KEYS[1];
  for (let i = 0; i < KEYS.length - 1; i++) {
    if (p >= KEYS[i].p && p <= KEYS[i + 1].p) { a = KEYS[i]; b = KEYS[i + 1]; break; }
  }
  const span = b.p - a.p;
  const local = span > 0 ? (p - a.p) / span : 0;
  const e = local * local * (3 - 2 * local);
  return {
    shoulder: a.pose.shoulder + (b.pose.shoulder - a.pose.shoulder) * e,
    elbow:    a.pose.elbow    + (b.pose.elbow    - a.pose.elbow)    * e,
    wrist:    a.pose.wrist    + (b.pose.wrist    - a.pose.wrist)    * e,
  };
}

// Central hub — single substantial machine body that slowly rotates
// around Y, with internal pulse + counter-rotating ring accents.
function Hub({ spinRef }: { spinRef: React.RefObject<THREE.Group | null> }) {
  const innerRef = useRef<THREE.Mesh>(null);
  const ringARef = useRef<THREE.Mesh>(null);
  const ringBRef = useRef<THREE.Mesh>(null);

  useFrame((_, dt) => {
    if (spinRef.current) spinRef.current.rotation.y += dt * 0.06;
    if (innerRef.current) {
      const t = performance.now() * 0.001;
      innerRef.current.scale.setScalar(1 + Math.sin(t * 1.2) * 0.08);
    }
    if (ringARef.current) ringARef.current.rotation.z += dt * 0.35;
    if (ringBRef.current) ringBRef.current.rotation.z -= dt * 0.22;
  });

  return (
    <group ref={spinRef}>
      {/* Floor pedestal */}
      <mesh position={[0, 0.06, 0]}>
        <cylinderGeometry args={[1.0, 1.2, 0.12, 24]} />
        <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.45} />
      </mesh>
      <mesh position={[0, 0.06, 0]}>
        <cylinderGeometry args={[1.0, 1.2, 0.12, 24]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.06} />
      </mesh>

      {/* Mid column */}
      <mesh position={[0, 0.5, 0]}>
        <cylinderGeometry args={[0.55, 0.7, 0.7, 16]} />
        <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.55} />
      </mesh>
      <mesh position={[0, 0.5, 0]}>
        <cylinderGeometry args={[0.55, 0.7, 0.7, 16]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.08} />
      </mesh>

      {/* Upper turret */}
      <mesh position={[0, 1.15, 0]}>
        <cylinderGeometry args={[0.7, 0.55, 0.55, 16]} />
        <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.6} />
      </mesh>
      <mesh position={[0, 1.15, 0]}>
        <cylinderGeometry args={[0.7, 0.55, 0.55, 16]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.08} />
      </mesh>

      {/* Two counter-rotating rings — both cyan to keep the rig monochrome */}
      <mesh ref={ringARef} position={[0, 1.15, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.95, 0.018, 8, 48]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.7} />
      </mesh>
      <mesh ref={ringBRef} position={[0, 1.15, 0]} rotation={[Math.PI / 2, Math.PI / 6, 0]}>
        <torusGeometry args={[1.15, 0.012, 8, 56]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.5} />
      </mesh>

      {/* Antenna spire */}
      <mesh position={[0, 1.7, 0]}>
        <cylinderGeometry args={[0.02, 0.05, 0.55, 8]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.85} />
      </mesh>
      <mesh position={[0, 2.05, 0]}>
        <sphereGeometry args={[0.08, 12, 12]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.95} />
      </mesh>

      {/* Inner glow core — visible through the wireframes */}
      <mesh ref={innerRef} position={[0, 0.85, 0]}>
        <sphereGeometry args={[0.32, 20, 20]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.55} />
      </mesh>
    </group>
  );
}

function Factory() {
  const t0 = useRef(0);
  const hubRef = useRef<THREE.Group>(null);

  // Joint refs per arm
  const jointRefs = useRef(
    ARMS.map(() => ({
      shoulder: { current: null as THREE.Group | null },
      elbow:    { current: null as THREE.Group | null },
      wrist:    { current: null as THREE.Group | null },
    }))
  );

  useFrame(() => {
    t0.current += 1 / 60;  // rough — actual dt comes from useFrame's args but constant-step keeps cycles stable
    ARMS.forEach((cfg, idx) => {
      const local = t0.current + cfg.phase;
      const pose = poseFor(local, cfg.cycle);
      const j = jointRefs.current[idx];
      if (j.shoulder.current) j.shoulder.current.rotation.x = pose.shoulder;
      if (j.elbow.current)    j.elbow.current.rotation.x = -pose.elbow;
      if (j.wrist.current)    j.wrist.current.rotation.x = pose.wrist;
    });
  });

  return (
    <>
      <Hub spinRef={hubRef} />

      {/* Arms — all attached to the same hub, all the same accent color */}
      {ARMS.map((cfg, i) => {
        const refs = jointRefs.current[i];
        const ax = Math.sin(cfg.attachYaw) * 0.55;
        const az = Math.cos(cfg.attachYaw) * 0.55;
        return (
          <group key={cfg.id} position={[ax, cfg.attachY, az]} rotation={[0, cfg.attachYaw, 0]}>
            {/* Shoulder hub mount */}
            <mesh>
              <sphereGeometry args={[0.20, 12, 12]} />
              <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.75} />
            </mesh>

            <group ref={refs.shoulder}>
              {/* Upper arm */}
              <mesh position={[0, 0.55, 0]}>
                <boxGeometry args={[0.22, 1.05, 0.22]} />
                <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.7} />
              </mesh>
              <mesh position={[0, 0.55, 0]}>
                <boxGeometry args={[0.22, 1.05, 0.22]} />
                <meshBasicMaterial color={ACCENT} transparent opacity={0.08} />
              </mesh>
              <mesh position={[0, 1.1, 0]}>
                <sphereGeometry args={[0.14, 12, 12]} />
                <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.75} />
              </mesh>

              <group ref={refs.elbow} position={[0, 1.1, 0]}>
                {/* Forearm */}
                <mesh position={[0, 0.5, 0]}>
                  <boxGeometry args={[0.18, 1.0, 0.18]} />
                  <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.7} />
                </mesh>
                <mesh position={[0, 0.5, 0]}>
                  <boxGeometry args={[0.18, 1.0, 0.18]} />
                  <meshBasicMaterial color={ACCENT} transparent opacity={0.08} />
                </mesh>
                <mesh position={[0, 1.0, 0]}>
                  <sphereGeometry args={[0.11, 10, 10]} />
                  <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.75} />
                </mesh>

                <group ref={refs.wrist} position={[0, 1.0, 0]}>
                  {/* Wrist tip — small accent piece (no gripper fingers now since
                      there's nothing to grip) */}
                  <mesh position={[0, 0.18, 0]}>
                    <coneGeometry args={[0.12, 0.32, 12]} />
                    <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.85} />
                  </mesh>
                  <mesh position={[0, 0.18, 0]}>
                    <coneGeometry args={[0.12, 0.32, 12]} />
                    <meshBasicMaterial color={ACCENT} transparent opacity={0.10} />
                  </mesh>
                  {/* Glow at the tip */}
                  <mesh position={[0, 0.36, 0]}>
                    <sphereGeometry args={[0.05, 10, 10]} />
                    <meshBasicMaterial color={ACCENT} transparent opacity={0.95} />
                  </mesh>
                </group>
              </group>
            </group>
          </group>
        );
      })}
    </>
  );
}

function Scene() {
  const { camera } = useThree();
  useEffect(() => {
    camera.position.set(0, 2.6, 9.0);
    camera.lookAt(0, 1.4, 0);
    if ("aspect" in camera) (camera as THREE.PerspectiveCamera).updateProjectionMatrix();
  }, [camera]);
  return (
    <>
      <fog attach="fog" args={["#03030a", 8, 26]} />
      <Factory />
    </>
  );
}

export function RoboticFactory3D() {
  return (
    <div className="factory3d" aria-hidden>
      <Canvas
        camera={{ position: [0, 2.6, 9.0], fov: 38 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        dpr={[1, 2]}
      >
        <Scene />
      </Canvas>
    </div>
  );
}
