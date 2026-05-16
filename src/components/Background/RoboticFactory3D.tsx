import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import "./factory3d.css";

// A single industrial 6-axis robotic arm. Inspired by classic Universal
// Robots / KUKA designs — chunky joint housings, clean rectangular
// segments, one accent color. The arm cycles slowly through a sequence
// of poses (reach high → swing left → reach forward → fold up → rest)
// so it always feels purposeful instead of restless.
//
// No conveyor, no orbs, no rings — one machine in the middle of the
// scene, doing its job.

const ACCENT = "#7fd1d3";

// Segment lengths (Three.js units)
const BASE_HEIGHT = 0.35;
const COLUMN_HEIGHT = 0.75;    // J1 housing
const UPPER_ARM_LEN = 1.55;
const FOREARM_LEN = 1.40;
const WRIST_LEN = 0.30;
const TOOL_LEN = 0.25;

// Visual rendering helpers ----------------------------------------------

function WireBox({ size, color = ACCENT, opacity = 0.7 }: { size: [number, number, number]; color?: string; opacity?: number }) {
  return (
    <>
      <mesh>
        <boxGeometry args={size} />
        <meshBasicMaterial color={color} wireframe transparent opacity={opacity} />
      </mesh>
      <mesh>
        <boxGeometry args={size} />
        <meshBasicMaterial color={color} transparent opacity={opacity * 0.12} />
      </mesh>
    </>
  );
}

function WireCyl({ args, color = ACCENT, opacity = 0.7 }: { args: [number, number, number, number]; color?: string; opacity?: number }) {
  return (
    <>
      <mesh>
        <cylinderGeometry args={args} />
        <meshBasicMaterial color={color} wireframe transparent opacity={opacity} />
      </mesh>
      <mesh>
        <cylinderGeometry args={args} />
        <meshBasicMaterial color={color} transparent opacity={opacity * 0.12} />
      </mesh>
    </>
  );
}

function JointHub({ radius = 0.18, color = ACCENT }: { radius?: number; color?: string }) {
  return (
    <mesh>
      <sphereGeometry args={[radius, 16, 16]} />
      <meshBasicMaterial color={color} wireframe transparent opacity={0.78} />
    </mesh>
  );
}

// Cycle ------------------------------------------------------------------

type Pose = { j1: number; j2: number; j3: number; j4: number; j5: number };

// 6 keyframes the arm sweeps through. j1 = base yaw, j2 = shoulder pitch,
// j3 = elbow pitch, j4 = wrist roll (around forearm axis), j5 = wrist pitch.
// Smooth-step interpolation between adjacent keys.
const POSES: { p: number; pose: Pose }[] = [
  { p: 0.00, pose: { j1:  0.00, j2: -0.10, j3:  1.30, j4:  0.0,  j5:  0.20 } },  // rest
  { p: 0.18, pose: { j1:  0.55, j2:  0.45, j3:  0.55, j4:  0.4,  j5: -0.10 } },  // reach up-right
  { p: 0.34, pose: { j1:  0.55, j2:  0.45, j3:  0.55, j4: -0.6,  j5:  0.30 } },  // wrist articulate (inspect)
  { p: 0.50, pose: { j1: -0.45, j2:  0.30, j3:  0.95, j4:  0.0,  j5: -0.20 } },  // swing left, reach forward
  { p: 0.66, pose: { j1: -0.45, j2:  0.75, j3:  1.50, j4:  0.3,  j5: -0.40 } },  // reach down
  { p: 0.82, pose: { j1:  0.00, j2: -0.45, j3:  0.30, j4:  0.0,  j5:  0.10 } },  // reach high overhead
  { p: 1.00, pose: { j1:  0.00, j2: -0.10, j3:  1.30, j4:  0.0,  j5:  0.20 } },  // back to rest
];

function poseFor(t: number, cycle: number): Pose {
  const k = ((t % cycle) + cycle) % cycle;
  const p = k / cycle;
  let a = POSES[0], b = POSES[1];
  for (let i = 0; i < POSES.length - 1; i++) {
    if (p >= POSES[i].p && p <= POSES[i + 1].p) { a = POSES[i]; b = POSES[i + 1]; break; }
  }
  const span = b.p - a.p;
  const local = span > 0 ? (p - a.p) / span : 0;
  const e = local * local * (3 - 2 * local);
  const lerp = (av: number, bv: number) => av + (bv - av) * e;
  return {
    j1: lerp(a.pose.j1, b.pose.j1),
    j2: lerp(a.pose.j2, b.pose.j2),
    j3: lerp(a.pose.j3, b.pose.j3),
    j4: lerp(a.pose.j4, b.pose.j4),
    j5: lerp(a.pose.j5, b.pose.j5),
  };
}

const CYCLE_SECONDS = 14;

function Robot() {
  const t0 = useRef(0);
  const j1Ref = useRef<THREE.Group>(null);
  const j2Ref = useRef<THREE.Group>(null);
  const j3Ref = useRef<THREE.Group>(null);
  const j4Ref = useRef<THREE.Group>(null);
  const j5Ref = useRef<THREE.Group>(null);
  const tipGlowRef = useRef<THREE.Mesh>(null);

  useFrame((_, dt) => {
    t0.current += dt;
    const pose = poseFor(t0.current, CYCLE_SECONDS);
    if (j1Ref.current) j1Ref.current.rotation.y = pose.j1;
    if (j2Ref.current) j2Ref.current.rotation.x = pose.j2;
    if (j3Ref.current) j3Ref.current.rotation.x = -pose.j3;
    if (j4Ref.current) j4Ref.current.rotation.y = pose.j4;
    if (j5Ref.current) j5Ref.current.rotation.x = pose.j5;
    if (tipGlowRef.current) {
      const t = performance.now() * 0.001;
      tipGlowRef.current.scale.setScalar(1 + Math.sin(t * 2.0) * 0.18);
    }
  });

  return (
    <group position={[0, 0, 0]}>
      {/* Floor plate — wide flat base mounting the robot */}
      <group position={[0, BASE_HEIGHT / 2, 0]}>
        <WireCyl args={[0.55, 0.65, BASE_HEIGHT, 24]} opacity={0.55} />
      </group>

      {/* J1 — base yaw rotation. Everything above this rotates with j1. */}
      <group ref={j1Ref} position={[0, BASE_HEIGHT, 0]}>
        {/* J1 column housing */}
        <group position={[0, COLUMN_HEIGHT / 2, 0]}>
          <WireCyl args={[0.30, 0.38, COLUMN_HEIGHT, 16]} opacity={0.6} />
        </group>

        {/* Shoulder joint hub at top of column */}
        <group position={[0, COLUMN_HEIGHT, 0]}>
          <JointHub radius={0.26} />

          {/* J2 — shoulder pitch. Upper arm pivots around X here. */}
          <group ref={j2Ref}>
            {/* Upper arm — boxy segment going up from shoulder */}
            <group position={[0, UPPER_ARM_LEN / 2, 0]}>
              <WireBox size={[0.26, UPPER_ARM_LEN, 0.30]} />
            </group>

            {/* Elbow joint hub at top of upper arm */}
            <group position={[0, UPPER_ARM_LEN, 0]}>
              <JointHub radius={0.22} />

              {/* J3 — elbow pitch. Forearm pivots around X here. */}
              <group ref={j3Ref}>
                {/* Forearm */}
                <group position={[0, FOREARM_LEN / 2, 0]}>
                  <WireBox size={[0.22, FOREARM_LEN, 0.26]} />
                </group>

                {/* Wrist joint hub at end of forearm */}
                <group position={[0, FOREARM_LEN, 0]}>
                  <JointHub radius={0.16} />

                  {/* J4 — wrist roll (around forearm's axis, locally Y) */}
                  <group ref={j4Ref}>
                    {/* Wrist segment */}
                    <group position={[0, WRIST_LEN / 2, 0]}>
                      <WireCyl args={[0.12, 0.14, WRIST_LEN, 12]} opacity={0.7} />
                    </group>

                    {/* J5 — wrist pitch */}
                    <group ref={j5Ref} position={[0, WRIST_LEN, 0]}>
                      <JointHub radius={0.12} />
                      {/* End-effector tool — a tapered tip */}
                      <group position={[0, TOOL_LEN / 2, 0]}>
                        <mesh>
                          <coneGeometry args={[0.09, TOOL_LEN, 14]} />
                          <meshBasicMaterial color={ACCENT} wireframe transparent opacity={0.82} />
                        </mesh>
                        <mesh>
                          <coneGeometry args={[0.09, TOOL_LEN, 14]} />
                          <meshBasicMaterial color={ACCENT} transparent opacity={0.10} />
                        </mesh>
                      </group>
                      {/* Pulsing glow bead at the very tip */}
                      <mesh ref={tipGlowRef} position={[0, TOOL_LEN + 0.06, 0]}>
                        <sphereGeometry args={[0.055, 12, 12]} />
                        <meshBasicMaterial color={ACCENT} transparent opacity={0.95} />
                      </mesh>
                    </group>
                  </group>
                </group>
              </group>
            </group>
          </group>
        </group>
      </group>
    </group>
  );
}

function Scene() {
  const { camera } = useThree();
  useEffect(() => {
    // Slight three-quarter angle so the articulation reads in 3D, not flat-on.
    camera.position.set(2.2, 2.4, 8.5);
    camera.lookAt(0, 1.7, 0);
    if ("aspect" in camera) (camera as THREE.PerspectiveCamera).updateProjectionMatrix();
  }, [camera]);
  return (
    <>
      <fog attach="fog" args={["#03030a", 9, 24]} />
      <Robot />
    </>
  );
}

export function RoboticFactory3D() {
  return (
    <div className="factory3d" aria-hidden>
      <Canvas
        camera={{ position: [2.2, 2.4, 8.5], fov: 38 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        dpr={[1, 2]}
      >
        <Scene />
      </Canvas>
    </div>
  );
}
