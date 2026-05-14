import { Canvas, useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";

function Core() {
  const groupRef = useRef<THREE.Group>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const targetRot = useRef({ x: 0, y: 0 });

  useFrame((state, dt) => {
    // mouse-driven target rotation
    const m = state.mouse;
    targetRot.current.x = m.y * 0.4;
    targetRot.current.y = m.x * 0.6;

    if (groupRef.current) {
      groupRef.current.rotation.x += (targetRot.current.x - groupRef.current.rotation.x) * 0.04;
      groupRef.current.rotation.y += (targetRot.current.y - groupRef.current.rotation.y) * 0.04;
      // Constant spin on top of mouse offset
      groupRef.current.rotation.y += dt * 0.18;
      groupRef.current.rotation.x += dt * 0.06;
    }
    if (innerRef.current) {
      innerRef.current.rotation.x -= dt * 0.5;
      innerRef.current.rotation.z += dt * 0.35;
    }
  });

  const ringPositions = useMemo(() => {
    // Generate sparse particle positions on a sphere shell
    const N = 220;
    const arr = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      // Fibonacci sphere distribution
      const phi = Math.acos(1 - (2 * (i + 0.5)) / N);
      const theta = Math.PI * (1 + Math.sqrt(5)) * i;
      const r = 1.7;
      arr[i * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = r * Math.cos(phi);
    }
    return arr;
  }, []);

  return (
    <group ref={groupRef}>
      {/* Outer wireframe icosahedron — primary */}
      <mesh>
        <icosahedronGeometry args={[1.4, 1]} />
        <meshBasicMaterial color="#7fd1d3" wireframe transparent opacity={0.85} />
      </mesh>
      {/* Outer larger faint shell */}
      <mesh>
        <icosahedronGeometry args={[1.85, 0]} />
        <meshBasicMaterial color="#5b9dd9" wireframe transparent opacity={0.18} />
      </mesh>
      {/* Inner counter-rotating geometry */}
      <mesh ref={innerRef}>
        <octahedronGeometry args={[0.55, 0]} />
        <meshBasicMaterial color="#ffc000" wireframe transparent opacity={0.9} />
      </mesh>
      {/* Glow core */}
      <mesh>
        <sphereGeometry args={[0.28, 32, 32]} />
        <meshBasicMaterial color="#aef5f8" transparent opacity={0.85} />
      </mesh>
      {/* Sparse particle shell */}
      <points>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[ringPositions, 3]}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.03}
          color="#aef5f8"
          transparent
          opacity={0.7}
          sizeAttenuation
        />
      </points>
    </group>
  );
}

function Lights() {
  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[3, 3, 5]} intensity={1.2} color="#7fd1d3" />
      <pointLight position={[-3, -2, -3]} intensity={0.6} color="#ffc000" />
    </>
  );
}

export function WireframeCore() {
  return (
    <div className="wireframe-core">
      <Canvas
        camera={{ position: [0, 0, 5], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
        dpr={[1, 2]}
      >
        <Lights />
        <Core />
      </Canvas>
      {/* Soft glow halo behind */}
      <div className="wireframe-halo" aria-hidden />
    </div>
  );
}
