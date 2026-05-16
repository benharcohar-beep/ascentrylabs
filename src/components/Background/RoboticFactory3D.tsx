import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import "./factory3d.css";

// A single central AI processing rig. One substantial wireframe hub
// in the middle of the scene with four articulated arms radiating
// from it at different angles. A continuous stream of glowing energy
// orbs flows along an invisible conveyor in front of the rig; arms
// reach out, claim a passing orb when their gripper closes, lift +
// hold + release back onto the conveyor downstream with a brief
// "processed" flash. Far more focused than five arms scattered
// across the floor.

type Hue = "cyan" | "blue" | "gold";
const HUE_COLOR: Record<Hue, string> = {
  cyan: "#7fd1d3",
  blue: "#5b9dd9",
  gold: "#ffc000",
};

// Each arm is one branch off the central hub. attachYaw = its angle
// around the hub (radians, 0 = forward). The pickX is computed once
// from yaw + reach so the orb-claim logic knows where this arm picks.
type ArmConfig = {
  id: string;
  attachYaw: number;       // radians, around hub Y
  attachY: number;         // height on hub where arm attaches
  phase: number;
  cycle: number;
  hue: Hue;
};

const ARM_REACH = 1.9;  // horizontal forward distance from hub center to gripper at pick pose

const ARMS: ArmConfig[] = [
  { id: "A1", attachYaw: -0.95, attachY: 0.9, phase:  0.0, cycle: 6.0, hue: "cyan" },
  { id: "A2", attachYaw: -0.32, attachY: 1.4, phase: -1.6, cycle: 7.5, hue: "blue" },
  { id: "A3", attachYaw:  0.32, attachY: 1.4, phase: -3.0, cycle: 7.0, hue: "gold" },
  { id: "A4", attachYaw:  0.95, attachY: 0.9, phase: -4.8, cycle: 6.5, hue: "cyan" },
];

// Conveyor parameters
const CONVEYOR_Z = 1.45;
const CONVEYOR_Y = 0.55;
const CONVEYOR_X_MIN = -14;
const CONVEYOR_X_MAX = 14;
const ORB_SPEED = 0.9;
const NUM_ORBS = 14;
const PICK_X_TOLERANCE = 0.6;
const PICK_Z_THRESHOLD = 1.0;

type Pose = { shoulder: number; elbow: number; wrist: number; grip: number };

// Cycle keyframes — pick down toward conveyor, lift, hold, return,
// release at the same point further downstream.
const KEYS = [
  { p: 0.00, pose: { shoulder: -0.20, elbow: 1.10, wrist:  0.20, grip: 1.0 } },
  { p: 0.18, pose: { shoulder:  0.65, elbow: 1.55, wrist: -0.40, grip: 1.0 } },
  { p: 0.28, pose: { shoulder:  0.65, elbow: 1.55, wrist: -0.40, grip: 0.0 } },
  { p: 0.42, pose: { shoulder:  0.10, elbow: 0.70, wrist: -0.15, grip: 0.0 } },
  { p: 0.58, pose: { shoulder:  0.30, elbow: 1.10, wrist:  0.15, grip: 0.0 } },
  { p: 0.72, pose: { shoulder:  0.65, elbow: 1.55, wrist: -0.40, grip: 0.0 } },
  { p: 0.78, pose: { shoulder:  0.65, elbow: 1.55, wrist: -0.40, grip: 1.0 } },
  { p: 0.92, pose: { shoulder: -0.20, elbow: 1.10, wrist:  0.20, grip: 1.0 } },
  { p: 1.00, pose: { shoulder: -0.20, elbow: 1.10, wrist:  0.20, grip: 1.0 } },
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
    grip:     a.pose.grip     + (b.pose.grip     - a.pose.grip)     * e,
  };
}

type OrbState = { ownedByArm: string | null; flashUntil: number; hue: Hue };
type ArmRuntime = {
  cfg: ArmConfig;
  wristRef: { current: THREE.Group | null };
  heldOrbId: number | null;
  pickX: number;          // computed from attachYaw + reach
};

function EnergyOrb({ color }: { color: string }) {
  return (
    <group>
      <mesh>
        <sphereGeometry args={[0.32, 14, 14]} />
        <meshBasicMaterial color={color} transparent opacity={0.10} depthWrite={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.22, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.32} depthWrite={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.15, 18, 18]} />
        <meshBasicMaterial color={color} transparent opacity={0.75} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.95} />
      </mesh>
    </group>
  );
}

// Central hub — substantial machine body with internal glow.
// Slowly spins on its Y axis so it feels alive even when arms idle.
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
      {/* Floor pedestal — wide */}
      <mesh position={[0, 0.06, 0]}>
        <cylinderGeometry args={[1.0, 1.2, 0.12, 24]} />
        <meshBasicMaterial color="#7fd1d3" wireframe transparent opacity={0.45} />
      </mesh>
      <mesh position={[0, 0.06, 0]}>
        <cylinderGeometry args={[1.0, 1.2, 0.12, 24]} />
        <meshBasicMaterial color="#7fd1d3" transparent opacity={0.06} />
      </mesh>

      {/* Mid column */}
      <mesh position={[0, 0.5, 0]}>
        <cylinderGeometry args={[0.55, 0.7, 0.7, 16]} />
        <meshBasicMaterial color="#7fd1d3" wireframe transparent opacity={0.55} />
      </mesh>
      <mesh position={[0, 0.5, 0]}>
        <cylinderGeometry args={[0.55, 0.7, 0.7, 16]} />
        <meshBasicMaterial color="#7fd1d3" transparent opacity={0.08} />
      </mesh>

      {/* Upper turret — the part the arms attach to */}
      <mesh position={[0, 1.15, 0]}>
        <cylinderGeometry args={[0.7, 0.55, 0.55, 16]} />
        <meshBasicMaterial color="#7fd1d3" wireframe transparent opacity={0.6} />
      </mesh>
      <mesh position={[0, 1.15, 0]}>
        <cylinderGeometry args={[0.7, 0.55, 0.55, 16]} />
        <meshBasicMaterial color="#7fd1d3" transparent opacity={0.08} />
      </mesh>

      {/* Two counter-rotating angular rings around the turret — pure visual flourish */}
      <mesh ref={ringARef} position={[0, 1.15, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.95, 0.018, 8, 48]} />
        <meshBasicMaterial color="#aef5f8" transparent opacity={0.7} />
      </mesh>
      <mesh ref={ringBRef} position={[0, 1.15, 0]} rotation={[Math.PI / 2, Math.PI / 6, 0]}>
        <torusGeometry args={[1.15, 0.012, 8, 56]} />
        <meshBasicMaterial color="#ffc000" transparent opacity={0.45} />
      </mesh>

      {/* Antenna / status spire on top */}
      <mesh position={[0, 1.7, 0]}>
        <cylinderGeometry args={[0.02, 0.05, 0.55, 8]} />
        <meshBasicMaterial color="#aef5f8" transparent opacity={0.85} />
      </mesh>
      <mesh position={[0, 2.05, 0]}>
        <sphereGeometry args={[0.08, 12, 12]} />
        <meshBasicMaterial color="#aef5f8" transparent opacity={0.95} />
      </mesh>

      {/* Inner glow core — visible through the wireframes */}
      <mesh ref={innerRef} position={[0, 0.85, 0]}>
        <sphereGeometry args={[0.32, 20, 20]} />
        <meshBasicMaterial color="#aef5f8" transparent opacity={0.55} />
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
      fingerL:  { current: null as THREE.Group | null },
      fingerR:  { current: null as THREE.Group | null },
    }))
  );

  // Arm runtimes (held orb tracking + pickX cache)
  const armRuntimes = useRef<ArmRuntime[]>(
    ARMS.map((cfg) => ({
      cfg,
      wristRef: { current: null },
      heldOrbId: null,
      // pickX = where the gripper's WORLD x is when this arm is at full reach.
      // With hub at origin and arm rotated by attachYaw, forward direction
      // points at (sin(yaw), 0, cos(yaw)). Gripper world position projects
      // along that direction by ARM_REACH.
      pickX: Math.sin(cfg.attachYaw) * ARM_REACH,
    }))
  );

  // Orbs
  const orbs = useRef<OrbState[]>(
    Array.from({ length: NUM_ORBS }, (_, i) => ({
      ownedByArm: null,
      flashUntil: 0,
      hue: (["cyan", "blue", "gold"] as Hue[])[i % 3],
    }))
  );
  const orbPositions = useRef<THREE.Vector3[]>(
    Array.from({ length: NUM_ORBS }, (_, i) => {
      const spacing = (CONVEYOR_X_MAX - CONVEYOR_X_MIN) / NUM_ORBS;
      return new THREE.Vector3(CONVEYOR_X_MIN + i * spacing, CONVEYOR_Y, CONVEYOR_Z);
    })
  );
  const orbRefs = useRef<(THREE.Group | null)[]>([]);

  // Tie wrist refs into runtime after first render
  useEffect(() => {
    armRuntimes.current.forEach((rt, i) => {
      rt.wristRef = jointRefs.current[i].wrist;
    });
  }, []);

  const gripperTmp = useMemo(() => new THREE.Vector3(), []);

  useFrame((_, dt) => {
    t0.current += dt;
    const now = performance.now();

    // Update each arm's pose + handle orb pickup/release
    armRuntimes.current.forEach((rt, idx) => {
      const local = t0.current + rt.cfg.phase;
      const pose = poseFor(local, rt.cfg.cycle);
      const j = jointRefs.current[idx];
      if (j.shoulder.current) j.shoulder.current.rotation.x = pose.shoulder;
      if (j.elbow.current) j.elbow.current.rotation.x = -pose.elbow;
      if (j.wrist.current) j.wrist.current.rotation.x = pose.wrist;
      if (j.fingerL.current) j.fingerL.current.rotation.x = -0.5 * pose.grip;
      if (j.fingerR.current) j.fingerR.current.rotation.x =  0.5 * pose.grip;

      if (pose.grip < 0.35) {
        if (rt.heldOrbId === null) {
          for (let oi = 0; oi < NUM_ORBS; oi++) {
            const o = orbs.current[oi];
            if (o.ownedByArm !== null) continue;
            const pos = orbPositions.current[oi];
            if (Math.abs(pos.x - rt.pickX) < PICK_X_TOLERANCE && pos.z > PICK_Z_THRESHOLD) {
              o.ownedByArm = rt.cfg.id;
              rt.heldOrbId = oi;
              break;
            }
          }
        }
        if (rt.heldOrbId !== null && rt.wristRef.current) {
          rt.wristRef.current.getWorldPosition(gripperTmp);
          gripperTmp.y -= 0.34;
          orbPositions.current[rt.heldOrbId].copy(gripperTmp);
        }
      } else {
        if (rt.heldOrbId !== null) {
          orbs.current[rt.heldOrbId].ownedByArm = null;
          orbs.current[rt.heldOrbId].flashUntil = now + 700;
          rt.heldOrbId = null;
        }
      }
    });

    // Orb positions
    for (let oi = 0; oi < NUM_ORBS; oi++) {
      const o = orbs.current[oi];
      const pos = orbPositions.current[oi];
      if (o.ownedByArm === null) {
        pos.x += ORB_SPEED * dt;
        if (pos.x > CONVEYOR_X_MAX) pos.x = CONVEYOR_X_MIN;
        pos.y += (CONVEYOR_Y - pos.y) * Math.min(1, dt * 4);
        pos.z += (CONVEYOR_Z - pos.z) * Math.min(1, dt * 4);
      }
      const ref = orbRefs.current[oi];
      if (ref) {
        ref.position.copy(pos);
        const flashK = Math.max(0, Math.min(1, (o.flashUntil - now) / 700));
        const glow = 1 + flashK * 0.8;
        ref.scale.setScalar(1 + flashK * 0.25);
        ref.children.forEach((child, ci) => {
          const mat = (child as THREE.Mesh).material as THREE.MeshBasicMaterial;
          if (!mat) return;
          const base = [0.10, 0.32, 0.75, 0.95][ci] ?? 0.5;
          mat.opacity = Math.min(1, base * glow);
        });
      }
    }
  });

  return (
    <>
      {/* Orbs */}
      {orbs.current.map((o, i) => (
        <group key={i} ref={(el) => { orbRefs.current[i] = el; }}>
          <EnergyOrb color={HUE_COLOR[o.hue]} />
        </group>
      ))}

      {/* Central hub */}
      <Hub spinRef={hubRef} />

      {/* Arms — all attached to the same hub. Position them on the hub's
          attachment ring and yaw them outward. The slow hub spin in <Hub>
          is intentionally independent of these arms; arms stay in their
          fixed yaws so their pickX remains aligned with conveyor positions. */}
      {ARMS.map((cfg, i) => {
        const color = HUE_COLOR[cfg.hue];
        const refs = jointRefs.current[i];
        const ax = Math.sin(cfg.attachYaw) * 0.55;   // x on hub perimeter
        const az = Math.cos(cfg.attachYaw) * 0.55;   // z on hub perimeter
        return (
          <group key={cfg.id} position={[ax, cfg.attachY, az]} rotation={[0, cfg.attachYaw, 0]}>
            {/* Shoulder hub mount — a small accent piece anchoring the arm to the body */}
            <mesh position={[0, 0, 0]}>
              <sphereGeometry args={[0.20, 12, 12]} />
              <meshBasicMaterial color={color} wireframe transparent opacity={0.75} />
            </mesh>

            <group ref={refs.shoulder}>
              <mesh position={[0, 0.55, 0]}>
                <boxGeometry args={[0.22, 1.05, 0.22]} />
                <meshBasicMaterial color={color} wireframe transparent opacity={0.7} />
              </mesh>
              <mesh position={[0, 0.55, 0]}>
                <boxGeometry args={[0.22, 1.05, 0.22]} />
                <meshBasicMaterial color={color} transparent opacity={0.08} />
              </mesh>
              <mesh position={[0, 1.1, 0]}>
                <sphereGeometry args={[0.14, 12, 12]} />
                <meshBasicMaterial color={color} wireframe transparent opacity={0.75} />
              </mesh>

              <group ref={refs.elbow} position={[0, 1.1, 0]}>
                <mesh position={[0, 0.5, 0]}>
                  <boxGeometry args={[0.18, 1.0, 0.18]} />
                  <meshBasicMaterial color={color} wireframe transparent opacity={0.7} />
                </mesh>
                <mesh position={[0, 0.5, 0]}>
                  <boxGeometry args={[0.18, 1.0, 0.18]} />
                  <meshBasicMaterial color={color} transparent opacity={0.08} />
                </mesh>
                <mesh position={[0, 1.0, 0]}>
                  <sphereGeometry args={[0.11, 10, 10]} />
                  <meshBasicMaterial color={color} wireframe transparent opacity={0.75} />
                </mesh>

                <group ref={refs.wrist} position={[0, 1.0, 0]}>
                  <mesh position={[0, 0.14, 0]}>
                    <boxGeometry args={[0.22, 0.14, 0.22]} />
                    <meshBasicMaterial color={color} wireframe transparent opacity={0.8} />
                  </mesh>
                  <group ref={refs.fingerL} position={[-0.07, 0.22, 0]}>
                    <mesh position={[0, 0.12, 0]}>
                      <boxGeometry args={[0.06, 0.24, 0.08]} />
                      <meshBasicMaterial color={color} wireframe transparent opacity={0.85} />
                    </mesh>
                  </group>
                  <group ref={refs.fingerR} position={[0.07, 0.22, 0]}>
                    <mesh position={[0, 0.12, 0]}>
                      <boxGeometry args={[0.06, 0.24, 0.08]} />
                      <meshBasicMaterial color={color} wireframe transparent opacity={0.85} />
                    </mesh>
                  </group>
                </group>
              </group>
            </group>
          </group>
        );
      })}

      <ConveyorLine />
    </>
  );
}

function ConveyorLine() {
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const verts = new Float32Array([
      CONVEYOR_X_MIN, CONVEYOR_Y - 0.18, CONVEYOR_Z - 0.16, CONVEYOR_X_MAX, CONVEYOR_Y - 0.18, CONVEYOR_Z - 0.16,
      CONVEYOR_X_MIN, CONVEYOR_Y - 0.18, CONVEYOR_Z + 0.16, CONVEYOR_X_MAX, CONVEYOR_Y - 0.18, CONVEYOR_Z + 0.16,
    ]);
    g.setAttribute("position", new THREE.BufferAttribute(verts, 3));
    return g;
  }, []);
  return (
    <lineSegments geometry={geom}>
      <lineBasicMaterial color="#7fd1d3" transparent opacity={0.18} />
    </lineSegments>
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
