import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import "./factory3d.css";

// 3D wireframe factory floor in WebGL. Each arm runs a continuous
// pick → lift → swing → place → return cycle AND owns its own crate,
// which travels in from the conveyor approach, gets attached to the
// gripper while held, releases at the placement zone, and fades out
// before respawning on the next cycle.

type ArmConfig = {
  id: string;
  position: [number, number, number];
  scale: number;
  phase: number;
  cycle: number;
  baseYaw: number;
  hue: "cyan" | "blue" | "gold";
};

const ARMS: ArmConfig[] = [
  { id: "A1", position: [-7,   0, -1],  scale: 1.0,  phase: 0,    cycle: 9,  baseYaw: -0.2,  hue: "cyan" },
  { id: "A2", position: [-3.6, 0,  0],  scale: 0.9,  phase: -2.4, cycle: 8,  baseYaw:  0.1,  hue: "blue" },
  { id: "A3", position: [ 0,   0, -1],  scale: 1.1, phase: -4.6, cycle: 10, baseYaw: -0.05, hue: "cyan" },
  { id: "A4", position: [ 3.6, 0,  0],  scale: 0.85, phase: -1.1, cycle: 9,  baseYaw:  0.18, hue: "gold" },
  { id: "A5", position: [ 7,   0, -1],  scale: 1.0,  phase: -6,   cycle: 11, baseYaw: -0.15, hue: "cyan" },
];

const HUE_COLOR = {
  cyan: "#7fd1d3",
  blue: "#5b9dd9",
  gold: "#ffc000",
};

type Pose = { baseYaw: number; shoulder: number; elbow: number; wrist: number; grip: number };

const KEYS = [
  { p: 0.00, pose: { baseYaw: 0,    shoulder: -0.18, elbow: 1.15, wrist:  0.00, grip: 0.55 } },
  { p: 0.18, pose: { baseYaw: 0,    shoulder:  0.55, elbow: 1.50, wrist: -0.35, grip: 0.55 } },
  { p: 0.28, pose: { baseYaw: 0,    shoulder:  0.55, elbow: 1.50, wrist: -0.35, grip: 0.05 } },
  { p: 0.42, pose: { baseYaw: 0,    shoulder:  0.10, elbow: 0.55, wrist: -0.10, grip: 0.05 } },
  { p: 0.58, pose: { baseYaw: 1.05, shoulder: -0.05, elbow: 0.80, wrist:  0.25, grip: 0.05 } },
  { p: 0.72, pose: { baseYaw: 1.05, shoulder:  0.40, elbow: 1.30, wrist:  0.25, grip: 0.05 } },
  { p: 0.78, pose: { baseYaw: 1.05, shoulder:  0.40, elbow: 1.30, wrist:  0.25, grip: 0.55 } },
  { p: 0.92, pose: { baseYaw: 0,    shoulder: -0.18, elbow: 1.15, wrist:  0.00, grip: 0.55 } },
  { p: 1.00, pose: { baseYaw: 0,    shoulder: -0.18, elbow: 1.15, wrist:  0.00, grip: 0.55 } },
];

function poseFor(t: number, cycle: number, baseYawBias: number): Pose {
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
    baseYaw:  baseYawBias + (a.pose.baseYaw  + (b.pose.baseYaw  - a.pose.baseYaw)  * e),
    shoulder: a.pose.shoulder + (b.pose.shoulder - a.pose.shoulder) * e,
    elbow:    a.pose.elbow    + (b.pose.elbow    - a.pose.elbow)    * e,
    wrist:    a.pose.wrist    + (b.pose.wrist    - a.pose.wrist)    * e,
    grip:     a.pose.grip     + (b.pose.grip     - a.pose.grip)     * e,
  };
}

// Returns the normalized cycle phase 0..1 for a given time
function phaseFor(t: number, cycle: number): number {
  const k = ((t % cycle) + cycle) % cycle;
  return k / cycle;
}

function ArmUnit({ cfg, t0 }: { cfg: ArmConfig; t0: React.MutableRefObject<number> }) {
  const baseRef = useRef<THREE.Group>(null);
  const shoulderRef = useRef<THREE.Group>(null);
  const elbowRef = useRef<THREE.Group>(null);
  const wristRef = useRef<THREE.Group>(null);
  const fingerLRef = useRef<THREE.Group>(null);
  const fingerRRef = useRef<THREE.Group>(null);
  const grippedRef = useRef<THREE.Group>(null);     // node parented to wrist; the crate while held
  const freeRef = useRef<THREE.Group>(null);        // node in world space; the crate while traveling / placed
  const tmpVec = useRef(new THREE.Vector3());
  const color = HUE_COLOR[cfg.hue];

  useFrame(() => {
    const local = t0.current + cfg.phase;
    const pose = poseFor(local, cfg.cycle, cfg.baseYaw);
    const phase = phaseFor(local, cfg.cycle);

    if (baseRef.current) baseRef.current.rotation.y = pose.baseYaw;
    if (shoulderRef.current) shoulderRef.current.rotation.x = pose.shoulder;
    if (elbowRef.current) elbowRef.current.rotation.x = -pose.elbow;
    if (wristRef.current) wristRef.current.rotation.x = pose.wrist;
    if (fingerLRef.current) fingerLRef.current.rotation.x = -pose.grip;
    if (fingerRRef.current) fingerRRef.current.rotation.x =  pose.grip;

    // Crate state machine driven by cycle phase:
    //   0.00–0.18 : APPROACH — crate slides in from the right on the
    //               conveyor toward the pick zone
    //   0.18–0.28 : SETTLE — crate sits in pick zone while arm closes grip
    //   0.28–0.78 : HELD — crate attached to gripper (parented under wrist)
    //   0.78–0.92 : PLACED — crate sits in placement zone after release
    //   0.92–1.00 : FADE — crate fades out, ready to respawn
    const held = phase >= 0.28 && phase < 0.78;

    if (grippedRef.current) {
      grippedRef.current.visible = held;
    }
    if (freeRef.current) {
      freeRef.current.visible = !held;

      // Approach: from x=+2.5 (right of arm) to x=0 (pick zone) over phase 0..0.18
      if (phase < 0.18) {
        const k = phase / 0.18;
        const x = 2.5 - 2.5 * k;
        freeRef.current.position.set(x, 0.18, 1.4);
        setOpacity(freeRef.current, 1);
      } else if (phase < 0.28) {
        // Settle in pick zone
        freeRef.current.position.set(0, 0.18, 1.4);
        setOpacity(freeRef.current, 1);
      } else if (phase < 0.78) {
        // Held — invisible (the grippedRef is shown instead)
        setOpacity(freeRef.current, 0);
      } else if (phase < 0.92) {
        // Placed — sits at placement zone (behind the arm relative to camera)
        freeRef.current.position.set(0, 0.18, -1.6);
        setOpacity(freeRef.current, 1);
      } else {
        // Fade
        const k = (phase - 0.92) / 0.08;
        freeRef.current.position.set(0, 0.18, -1.6);
        setOpacity(freeRef.current, 1 - k);
      }
    }

    // Light up gripper while holding
    if (grippedRef.current && held) {
      // Position the held crate just below the wrist (gripper tip is ~0.34 below wrist origin)
      grippedRef.current.position.set(0, -0.34, 0);
    }
    // suppress unused warning
    void tmpVec;
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

      {/* Crate while free (in world / arm-local space) */}
      <group ref={freeRef}>
        <Crate color="#aef5f8" />
      </group>

      {/* Base column — rotates in yaw */}
      <group ref={baseRef} position={[0, 0.18, 0]}>
        <mesh position={[0, 0.18, 0]}>
          <cylinderGeometry args={[0.22, 0.28, 0.36, 12]} />
          <meshBasicMaterial color={color} wireframe transparent opacity={0.65} />
        </mesh>
        <mesh position={[0, 0.38, 0]}>
          <sphereGeometry args={[0.18, 12, 12]} />
          <meshBasicMaterial color={color} wireframe transparent opacity={0.75} />
        </mesh>

        <group ref={shoulderRef} position={[0, 0.38, 0]}>
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

          <group ref={elbowRef} position={[0, 1.2, 0]}>
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

            <group ref={wristRef} position={[0, 1.0, 0]}>
              <mesh position={[0, 0.14, 0]}>
                <boxGeometry args={[0.22, 0.14, 0.22]} />
                <meshBasicMaterial color={color} wireframe transparent opacity={0.8} />
              </mesh>

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

              {/* Crate while held — parented under the wrist so it follows automatically */}
              <group ref={grippedRef} position={[0, -0.34, 0]}>
                <Crate color="#aef5f8" />
              </group>
            </group>
          </group>
        </group>
      </group>
    </group>
  );
}

// Helper: set opacity on every mesh material inside a group
function setOpacity(group: THREE.Group, opacity: number) {
  group.traverse((child) => {
    if ((child as THREE.Mesh).isMesh) {
      const mat = (child as THREE.Mesh).material as THREE.Material;
      mat.opacity = opacity;
      mat.transparent = true;
    }
  });
}

function Crate({ color }: { color: string }) {
  return (
    <>
      <mesh>
        <boxGeometry args={[0.32, 0.22, 0.28]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.85} />
      </mesh>
      <mesh>
        <boxGeometry args={[0.32, 0.22, 0.28]} />
        <meshBasicMaterial color={color} transparent opacity={0.12} />
      </mesh>
    </>
  );
}

function Scene() {
  const { camera } = useThree();
  const t0 = useRef(0);

  // Explicit camera position + lookAt — pushes the visual horizon higher
  // in the frame so arms sit comfortably in the lower half of the viewport.
  useEffect(() => {
    camera.position.set(0, 2.4, 8.5);
    camera.lookAt(0, 1.6, 0);
    if ("aspect" in camera) {
      (camera as THREE.PerspectiveCamera).updateProjectionMatrix();
    }
  }, [camera]);

  useFrame((_, dt) => { t0.current += dt; });

  return (
    <>
      <fog attach="fog" args={["#03030a", 8, 26]} />
      {ARMS.map((a) => (
        <ArmUnit key={a.id} cfg={a} t0={t0} />
      ))}
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
