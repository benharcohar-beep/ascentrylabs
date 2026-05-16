import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import "./factory3d.css";

// AI processing line. Glowing energy orbs flow continuously along an
// invisible horizontal conveyor in front of the arms. Each arm runs
// its own pick → lift → swing → release cycle, claiming a passing orb
// when its gripper closes and releasing it back downstream when the
// gripper opens. Released orbs flash brighter for a moment (signalling
// "processed") then continue traveling at conveyor speed.
//
// Reads as: data packets being inspected by an AI line. Cyan/blue/gold
// orbs on a dark wireframe stage. Far more on-brand for an AI
// consultancy than cardboard crates.

type Hue = "cyan" | "blue" | "gold";
const HUE_COLOR: Record<Hue, string> = {
  cyan: "#7fd1d3",
  blue: "#5b9dd9",
  gold: "#ffc000",
};

type ArmConfig = {
  id: string;
  position: [number, number, number];
  scale: number;
  phase: number;
  cycle: number;
  baseYaw: number;
  hue: Hue;
  pickX: number;     // world x where this arm picks orbs
};

const ARMS: ArmConfig[] = [
  { id: "A1", position: [-7,   0, -0.6], scale: 1.0,  phase: 0,    cycle: 7,  baseYaw: -0.1, hue: "cyan", pickX: -7   },
  { id: "A2", position: [-3.6, 0,  0.0], scale: 0.9,  phase: -1.6, cycle: 6,  baseYaw:  0.05, hue: "blue", pickX: -3.6 },
  { id: "A3", position: [ 0,   0, -0.6], scale: 1.1,  phase: -3.2, cycle: 7,  baseYaw:  0.0,  hue: "cyan", pickX:  0   },
  { id: "A4", position: [ 3.6, 0,  0.0], scale: 0.85, phase: -4.4, cycle: 6,  baseYaw: -0.05, hue: "gold", pickX:  3.6 },
  { id: "A5", position: [ 7,   0, -0.6], scale: 1.0,  phase: -5.5, cycle: 7,  baseYaw:  0.1,  hue: "cyan", pickX:  7   },
];

// Conveyor parameters
const CONVEYOR_Z = 1.45;
const CONVEYOR_Y = 0.55;
const CONVEYOR_X_MIN = -14;
const CONVEYOR_X_MAX = 14;
const ORB_SPEED = 0.9;             // units / second
const NUM_ORBS = 14;
const PICK_X_TOLERANCE = 0.7;      // arm grabs orbs within this x distance of pickX
const PICK_Z_THRESHOLD = 1.0;      // arm only grabs orbs that are on the conveyor (z > this)

type Pose = { shoulder: number; elbow: number; wrist: number; grip: number; baseYaw: number };

// Cycle keyframes — pick down toward conveyor (z=+1.45), lift, swing
// back over the arm to placement zone (negative z = behind), release.
// "grip" 1.0 = open, 0.0 = fully closed.
const KEYS = [
  { p: 0.00, pose: { shoulder: -0.20, elbow: 1.10, wrist:  0.20, grip: 1.0, baseYaw:  0.05 } },
  { p: 0.18, pose: { shoulder:  0.62, elbow: 1.55, wrist: -0.40, grip: 1.0, baseYaw:  0.05 } }, // reach down to conveyor
  { p: 0.28, pose: { shoulder:  0.62, elbow: 1.55, wrist: -0.40, grip: 0.0, baseYaw:  0.05 } }, // close grip
  { p: 0.42, pose: { shoulder:  0.10, elbow: 0.70, wrist: -0.15, grip: 0.0, baseYaw:  0.05 } }, // lift
  { p: 0.58, pose: { shoulder:  0.30, elbow: 1.10, wrist:  0.15, grip: 0.0, baseYaw:  0.05 } }, // hold high
  { p: 0.72, pose: { shoulder:  0.62, elbow: 1.55, wrist: -0.40, grip: 0.0, baseYaw:  0.05 } }, // back down to conveyor
  { p: 0.78, pose: { shoulder:  0.62, elbow: 1.55, wrist: -0.40, grip: 1.0, baseYaw:  0.05 } }, // open grip, release
  { p: 0.92, pose: { shoulder: -0.20, elbow: 1.10, wrist:  0.20, grip: 1.0, baseYaw:  0.05 } }, // return to rest
  { p: 1.00, pose: { shoulder: -0.20, elbow: 1.10, wrist:  0.20, grip: 1.0, baseYaw:  0.05 } },
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
    baseYaw:  a.pose.baseYaw  + (b.pose.baseYaw  - a.pose.baseYaw)  * e,
  };
}

// Shared mutable state for the whole scene — refs avoid React re-renders
type OrbState = {
  ownedByArm: string | null;
  flashUntil: number;     // performance.now() until which the orb glows brighter
  hue: Hue;
};

type ArmRuntime = {
  cfg: ArmConfig;
  wristRef: { current: THREE.Group | null };
  heldOrbId: number | null;
};

// Layered glowing sphere — bright core, colored shell, faint outer halo
function EnergyOrb({ color, glow = 1 }: { color: string; glow?: number }) {
  return (
    <group>
      {/* outermost halo */}
      <mesh>
        <sphereGeometry args={[0.32, 14, 14]} />
        <meshBasicMaterial color={color} transparent opacity={0.10 * glow} depthWrite={false} />
      </mesh>
      {/* mid halo */}
      <mesh>
        <sphereGeometry args={[0.22, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.32 * glow} depthWrite={false} />
      </mesh>
      {/* colored shell */}
      <mesh>
        <sphereGeometry args={[0.15, 18, 18]} />
        <meshBasicMaterial color={color} transparent opacity={0.75 * glow} />
      </mesh>
      {/* bright white core */}
      <mesh>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={Math.min(1, 0.95 * glow)} />
      </mesh>
    </group>
  );
}

function Factory() {
  const t0 = useRef(0);

  // Arms — refs to track which orb each is currently holding + pose targets
  const armRuntimes = useRef<ArmRuntime[]>(
    ARMS.map((cfg) => ({ cfg, wristRef: { current: null }, heldOrbId: null }))
  );

  // Orbs — mutable state. Each orb has a free-flowing position; index in
  // this array matches index in the rendered orb meshes.
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

  // Arm joint refs — one set per arm
  const jointRefs = useRef(
    ARMS.map(() => ({
      base: { current: null as THREE.Group | null },
      shoulder: { current: null as THREE.Group | null },
      elbow: { current: null as THREE.Group | null },
      wrist: { current: null as THREE.Group | null },
      fingerL: { current: null as THREE.Group | null },
      fingerR: { current: null as THREE.Group | null },
    }))
  );

  // Tie wrist refs into the runtime so the orb-claim logic can reach them
  useEffect(() => {
    armRuntimes.current.forEach((rt, i) => {
      rt.wristRef = jointRefs.current[i].wrist;
    });
  }, []);

  const gripperTmp = useMemo(() => new THREE.Vector3(), []);

  useFrame((_, dt) => {
    t0.current += dt;
    const now = performance.now();

    // 1) Advance each arm's pose + handle orb pickup/release
    armRuntimes.current.forEach((rt, idx) => {
      const local = t0.current + rt.cfg.phase;
      const pose = poseFor(local, rt.cfg.cycle);
      const joints = jointRefs.current[idx];
      if (joints.base.current) joints.base.current.rotation.y = pose.baseYaw + rt.cfg.baseYaw;
      if (joints.shoulder.current) joints.shoulder.current.rotation.x = pose.shoulder;
      if (joints.elbow.current) joints.elbow.current.rotation.x = -pose.elbow;
      if (joints.wrist.current) joints.wrist.current.rotation.x = pose.wrist;
      if (joints.fingerL.current) joints.fingerL.current.rotation.x = -0.5 * pose.grip;
      if (joints.fingerR.current) joints.fingerR.current.rotation.x =  0.5 * pose.grip;

      // Gripper closed → try to pick up a passing orb
      if (pose.grip < 0.35) {
        if (rt.heldOrbId === null) {
          // Find a free orb in our pick zone
          for (let oi = 0; oi < NUM_ORBS; oi++) {
            const o = orbs.current[oi];
            if (o.ownedByArm !== null) continue;
            const pos = orbPositions.current[oi];
            if (Math.abs(pos.x - rt.cfg.pickX) < PICK_X_TOLERANCE && pos.z > PICK_Z_THRESHOLD) {
              o.ownedByArm = rt.cfg.id;
              rt.heldOrbId = oi;
              break;
            }
          }
        }
        // If holding an orb, snap it to the gripper's world position
        if (rt.heldOrbId !== null && rt.wristRef.current) {
          rt.wristRef.current.getWorldPosition(gripperTmp);
          gripperTmp.y -= 0.34 * rt.cfg.scale;     // gripper tip offset (scaled)
          orbPositions.current[rt.heldOrbId].copy(gripperTmp);
        }
      } else {
        // Gripper opening / open → release any held orb, give it a flash
        if (rt.heldOrbId !== null) {
          orbs.current[rt.heldOrbId].ownedByArm = null;
          orbs.current[rt.heldOrbId].flashUntil = now + 700;
          rt.heldOrbId = null;
        }
      }
    });

    // 2) Update orb positions (free ones travel; held ones already snapped)
    for (let oi = 0; oi < NUM_ORBS; oi++) {
      const o = orbs.current[oi];
      const pos = orbPositions.current[oi];
      if (o.ownedByArm === null) {
        pos.x += ORB_SPEED * dt;
        if (pos.x > CONVEYOR_X_MAX) {
          pos.x = CONVEYOR_X_MIN;
        }
        // Drift back to the conveyor y/z (in case the arm released away from it)
        pos.y += (CONVEYOR_Y - pos.y) * Math.min(1, dt * 4);
        pos.z += (CONVEYOR_Z - pos.z) * Math.min(1, dt * 4);
      }
      // Sync rendered mesh
      const ref = orbRefs.current[oi];
      if (ref) {
        ref.position.copy(pos);
        // Apply flash glow if recently released
        const flashK = Math.max(0, Math.min(1, (o.flashUntil - now) / 700));
        const glow = 1 + flashK * 0.8;
        ref.scale.setScalar(1 + flashK * 0.25);
        // Update opacity via material — child mesh order matches EnergyOrb
        ref.children.forEach((child, ci) => {
          const mat = (child as THREE.Mesh).material as THREE.MeshBasicMaterial;
          if (!mat) return;
          // Boost halo opacity during flash
          const base = [0.10, 0.32, 0.75, 0.95][ci] ?? 0.5;
          mat.opacity = Math.min(1, base * glow);
        });
      }
    }
  });

  return (
    <>
      {/* Orbs — rendered as a flat list of groups */}
      {orbs.current.map((o, i) => (
        <group key={i} ref={(el) => { orbRefs.current[i] = el; }}>
          <EnergyOrb color={HUE_COLOR[o.hue]} />
        </group>
      ))}

      {/* Arms */}
      {ARMS.map((cfg, i) => {
        const color = HUE_COLOR[cfg.hue];
        const refs = jointRefs.current[i];
        return (
          <group key={cfg.id} position={cfg.position} scale={cfg.scale}>
            {/* Floor pedestal */}
            <mesh position={[0, 0.06, 0]}>
              <cylinderGeometry args={[0.42, 0.5, 0.12, 16]} />
              <meshBasicMaterial color={color} wireframe transparent opacity={0.55} />
            </mesh>
            <mesh position={[0, 0.06, 0]}>
              <cylinderGeometry args={[0.42, 0.5, 0.12, 16]} />
              <meshBasicMaterial color={color} transparent opacity={0.08} />
            </mesh>
            <group ref={refs.base} position={[0, 0.18, 0]}>
              <mesh position={[0, 0.18, 0]}>
                <cylinderGeometry args={[0.22, 0.28, 0.36, 12]} />
                <meshBasicMaterial color={color} wireframe transparent opacity={0.65} />
              </mesh>
              <mesh position={[0, 0.38, 0]}>
                <sphereGeometry args={[0.18, 12, 12]} />
                <meshBasicMaterial color={color} wireframe transparent opacity={0.75} />
              </mesh>
              <group ref={refs.shoulder} position={[0, 0.38, 0]}>
                <mesh position={[0, 0.6, 0]}>
                  <boxGeometry args={[0.22, 1.2, 0.22]} />
                  <meshBasicMaterial color={color} wireframe transparent opacity={0.7} />
                </mesh>
                <mesh position={[0, 0.6, 0]}>
                  <boxGeometry args={[0.22, 1.2, 0.22]} />
                  <meshBasicMaterial color={color} transparent opacity={0.08} />
                </mesh>
                <mesh position={[0, 1.2, 0]}>
                  <sphereGeometry args={[0.14, 12, 12]} />
                  <meshBasicMaterial color={color} wireframe transparent opacity={0.75} />
                </mesh>
                <group ref={refs.elbow} position={[0, 1.2, 0]}>
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
          </group>
        );
      })}

      {/* Faint conveyor trace line — gives the orbs a visible path without
          re-introducing the heavy slab that caused the horizon stripe */}
      <ConveyorLine />
    </>
  );
}

function ConveyorLine() {
  // Two thin parallel lines along the orbs' x track. Used only as a
  // subtle path indicator so the eye groups the orbs as "on a line".
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
    camera.position.set(0, 2.4, 8.5);
    camera.lookAt(0, 1.6, 0);
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
        camera={{ position: [0, 2.4, 8.5], fov: 38 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        dpr={[1, 2]}
      >
        <Scene />
      </Canvas>
    </div>
  );
}
