import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import "./factory3d.css";

// AI grid network. Orthogonal roadways spread across the y=0 plane;
// dozens of glowing pods race along them at varying speeds, each
// trailing a comet-like glow tail. Pods are color-tinted (cyan / blue
// / gold). Camera looks down at a 3/4 angle so the grid recedes into
// the fog like an aerial view of a self-driving city.
//
// All state lives in refs (no React re-renders per frame). Pods are
// rendered as instanced meshes for efficiency at the pod counts here.

const ACCENT = "#7fd1d3";

// Grid layout
const GRID_HALF = 9;          // grid spans -GRID_HALF to +GRID_HALF
const ROAD_POS_H = [-6, -3, 0, 3, 6];  // z values for horizontal roads
const ROAD_POS_V = [-6, -3, 0, 3, 6];  // x values for vertical roads

const HUES = ["#7fd1d3", "#5b9dd9", "#ffc000", "#aef5f8"] as const;

// Pod count
const PODS_PER_ROAD = 4;

type Road = {
  // Endpoint coordinates on the y=0 plane
  ax: number; az: number;
  bx: number; bz: number;
  length: number;
};

const ROADS: Road[] = [
  // Horizontal roads (constant z, varying x)
  ...ROAD_POS_H.map((z): Road => ({ ax: -GRID_HALF, az: z, bx: GRID_HALF, bz: z, length: 2 * GRID_HALF })),
  // Vertical roads (constant x, varying z)
  ...ROAD_POS_V.map((x): Road => ({ ax: x, az: -GRID_HALF, bx: x, bz: GRID_HALF, length: 2 * GRID_HALF })),
];

type Pod = {
  roadIdx: number;
  t: number;         // 0..1 along the road
  speed: number;     // units of t per second
  hue: string;
  direction: 1 | -1; // 1 = ab, -1 = ba
};

// Build the road lines geometry (drawn as faint lineSegments)
function useRoadGeometry() {
  return useMemo(() => {
    const verts: number[] = [];
    ROADS.forEach((r) => {
      verts.push(r.ax, 0.01, r.az, r.bx, 0.01, r.bz);
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(verts), 3));
    return geo;
  }, []);
}

// Build the intersection markers geometry (tiny diamonds where roads cross)
function useIntersectionGeometry() {
  return useMemo(() => {
    const positions: [number, number, number][] = [];
    ROAD_POS_H.forEach((z) => {
      ROAD_POS_V.forEach((x) => {
        positions.push([x, 0.02, z]);
      });
    });
    return positions;
  }, []);
}

function podWorldPosition(road: Road, t: number, out: THREE.Vector3) {
  out.x = road.ax + (road.bx - road.ax) * t;
  out.y = 0.18;
  out.z = road.az + (road.bz - road.az) * t;
  return out;
}

// Single glowing pod — bright core + 2 halo shells + 4 trailing dots.
// Sizes dialed down ~55% from the original so the swarm reads as
// ambient activity rather than crowding the background.
function PodMesh({ color, podRef }: { color: string; podRef: React.RefObject<THREE.Group | null> }) {
  return (
    <group ref={podRef}>
      {/* Pod head */}
      <mesh>
        <sphereGeometry args={[0.04, 10, 10]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.9} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.07, 10, 10]} />
        <meshBasicMaterial color={color} transparent opacity={0.45} depthWrite={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.11, 10, 10]} />
        <meshBasicMaterial color={color} transparent opacity={0.12} depthWrite={false} />
      </mesh>
    </group>
  );
}

function PodTrail({ color, trailRefs }: {
  color: string;
  trailRefs: React.MutableRefObject<(THREE.Mesh | null)[]>;
}) {
  // Four trailing beads with decreasing opacity — quieter than before
  const beads = [0, 1, 2, 3];
  const opacities = [0.30, 0.20, 0.12, 0.06];
  return (
    <>
      {beads.map((i) => (
        <mesh
          key={i}
          ref={(el) => { trailRefs.current[i] = el; }}
        >
          <sphereGeometry args={[0.04 - i * 0.008, 8, 8]} />
          <meshBasicMaterial color={color} transparent opacity={opacities[i]} depthWrite={false} />
        </mesh>
      ))}
    </>
  );
}

function Network() {
  const roadGeo = useRoadGeometry();
  const intersections = useIntersectionGeometry();

  // Build pod state — randomized speeds, hues, directions, start offsets
  const pods = useRef<Pod[]>([]);
  if (pods.current.length === 0) {
    const built: Pod[] = [];
    ROADS.forEach((_, roadIdx) => {
      for (let i = 0; i < PODS_PER_ROAD; i++) {
        built.push({
          roadIdx,
          t: Math.random(),
          speed: 0.05 + Math.random() * 0.12,   // slow → moderate
          hue: HUES[Math.floor(Math.random() * HUES.length)],
          direction: Math.random() < 0.5 ? 1 : -1,
        });
      }
    });
    pods.current = built;
  }

  // One group ref per pod (head) and four trail bead refs per pod
  const podGroupRefs = useRef<(THREE.Group | null)[]>([]);
  const trailRefs = useRef<(THREE.Mesh | null)[][]>(
    pods.current.map(() => [null, null, null, null])
  );
  // History buffer for trail positions (4 past world positions per pod)
  const history = useRef<THREE.Vector3[][]>(
    pods.current.map(() => [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()])
  );
  const tmp = useMemo(() => new THREE.Vector3(), []);
  const frameCounter = useRef(0);

  useFrame((_, dt) => {
    frameCounter.current++;
    pods.current.forEach((pod, i) => {
      // Advance along road
      pod.t += pod.speed * dt * pod.direction;
      // Wrap with direction logic — loop endpoints
      if (pod.t > 1) {
        pod.t = pod.t - 1;
      } else if (pod.t < 0) {
        pod.t = pod.t + 1;
      }
      const road = ROADS[pod.roadIdx];
      podWorldPosition(road, pod.t, tmp);
      const headEl = podGroupRefs.current[i];
      if (headEl) headEl.position.copy(tmp);

      // Update trail history every 3 frames so trail spreads visibly
      if (frameCounter.current % 3 === 0) {
        const hist = history.current[i];
        // shift trail history backward
        for (let k = hist.length - 1; k > 0; k--) hist[k].copy(hist[k - 1]);
        hist[0].copy(tmp);
      }
      // Render trail beads at history positions
      const trail = trailRefs.current[i];
      for (let k = 0; k < trail.length; k++) {
        const t = trail[k];
        const hist = history.current[i][k];
        if (t) t.position.copy(hist);
      }
    });
  });

  return (
    <>
      {/* Roads as faint lines on the y=0.01 plane */}
      <lineSegments geometry={roadGeo}>
        <lineBasicMaterial color={ACCENT} transparent opacity={0.32} />
      </lineSegments>

      {/* Intersection markers — small diamonds (planes rotated 45° around Y) */}
      {intersections.map(([x, y, z], i) => (
        <mesh key={i} position={[x, y, z]} rotation={[-Math.PI / 2, 0, Math.PI / 4]}>
          <planeGeometry args={[0.22, 0.22]} />
          <meshBasicMaterial color={ACCENT} transparent opacity={0.55} side={THREE.DoubleSide} />
        </mesh>
      ))}

      {/* Pods + their trail beads */}
      {pods.current.map((pod, i) => (
        <group key={i}>
          <PodMesh
            color={pod.hue}
            podRef={{ get current() { return podGroupRefs.current[i]; }, set current(v) { podGroupRefs.current[i] = v; } } as React.RefObject<THREE.Group | null>}
          />
          <PodTrail color={pod.hue} trailRefs={{ current: trailRefs.current[i] }} />
        </group>
      ))}
    </>
  );
}

function Scene() {
  const { camera } = useThree();
  useEffect(() => {
    // Aerial 3/4 angle looking down on the grid so roads recede into fog
    camera.position.set(0, 6.5, 9.5);
    camera.lookAt(0, 0, -1);
    if ("aspect" in camera) (camera as THREE.PerspectiveCamera).updateProjectionMatrix();
  }, [camera]);
  return (
    <>
      <fog attach="fog" args={["#03030a", 10, 28]} />
      <Network />
    </>
  );
}

export function RoboticFactory3D() {
  return (
    <div className="factory3d" aria-hidden>
      <Canvas
        camera={{ position: [0, 6.5, 9.5], fov: 38 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        dpr={[1, 2]}
      >
        <Scene />
      </Canvas>
    </div>
  );
}
