"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface MissionCoreProps {
  position: [number, number, number];
  status: string;
  progress: number;
  hasMemoryActivity: boolean;
}

export function MissionCore({ position, status, progress, hasMemoryActivity }: MissionCoreProps) {
  const groupRef = useRef<THREE.Group>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const innerRef = useRef<THREE.Mesh>(null);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    if (groupRef.current) {
      // Subtle rotation, not oversized or game-like
      groupRef.current.rotation.y += delta * 0.15;
    }
    if (coreRef.current) {
      // Gentle pulse based on progress
      const scale = 1 + Math.sin(t * 0.8) * 0.02;
      coreRef.current.scale.setScalar(scale);
    }
    if (innerRef.current) {
      innerRef.current.rotation.x += delta * 0.3;
      innerRef.current.rotation.y += delta * 0.2;
    }
    if (ringRef.current) {
      ringRef.current.rotation.z += delta * 0.25;
    }
  });

  const statusColor = useMemo(() => {
    switch (status) {
      case "running":
        return "#8b5cf6";
      case "completed":
        return "#10b981";
      case "awaiting_approval":
        return "#f59e0b";
      case "failed":
        return "#ef4444";
      case "paused":
        return "#71717a";
      default:
        return "#8b5cf6";
    }
  }, [status]);

  return (
    <group position={position} ref={groupRef}>
      {/* Central geometry - not oversized, physical material subtle */}
      <mesh ref={coreRef} castShadow={false} receiveShadow={false}>
        <sphereGeometry args={[0.65, 32, 32]} />
        <meshPhysicalMaterial
          color="#18181b"
          transmission={0.1}
          thickness={0.5}
          roughness={0.3}
          metalness={0.2}
          emissive={statusColor}
          emissiveIntensity={0.15}
          clearcoat={0.3}
        />
      </mesh>

      {/* Inner icosahedron - subtle */}
      <mesh ref={innerRef}>
        <icosahedronGeometry args={[0.35, 1]} />
        <meshStandardMaterial color={statusColor} wireframe transparent opacity={0.15} emissive={statusColor} emissiveIntensity={0.2} />
      </mesh>

      {/* Status ring - progress indicator */}
      <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.05, 0.02, 16, 100, (progress / 100) * Math.PI * 2]} />
        <meshStandardMaterial color={statusColor} emissive={statusColor} emissiveIntensity={0.4} transparent opacity={0.8} />
      </mesh>

      {/* Outer subtle ring */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.25, 0.008, 16, 64]} />
        <meshStandardMaterial color="#3f3f46" transparent opacity={0.3} />
      </mesh>

      {/* Memory indicator - small pulsing dots if activity */}
      {hasMemoryActivity && (
        <group>
          {[0, 1, 2].map((i) => (
            <mesh key={i} position={[Math.cos((i / 3) * Math.PI * 2) * 0.9, 0.2, Math.sin((i / 3) * Math.PI * 2) * 0.9]}>
              <sphereGeometry args={[0.03, 8, 8]} />
              <meshStandardMaterial color="#06b6d4" emissive="#06b6d4" emissiveIntensity={0.6} />
            </mesh>
          ))}
        </group>
      )}

      {/* Activity pulse - subtle, not gaming neon */}
      <mesh>
        <sphereGeometry args={[0.75, 16, 16]} />
        <meshBasicMaterial color={statusColor} transparent opacity={0.03} />
      </mesh>
    </group>
  );
}
