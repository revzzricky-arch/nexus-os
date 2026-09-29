"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface MissionCoreProps {
  position: [number, number, number];
  status: string;
  hasMemoryActivity: boolean; // abstract indicator, not raw DB
}

export function MissionCore({ position, status, hasMemoryActivity }: MissionCoreProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);

  useFrame((state, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.1;
    }
    if (innerRef.current) {
      innerRef.current.rotation.y -= delta * 0.2;
      innerRef.current.rotation.x += delta * 0.05;
    }
    if (ringRef.current) {
      ringRef.current.rotation.z += delta * 0.3;
      if (hasMemoryActivity) {
        // Abstract memory activity pulse
        const scale = 1 + Math.sin(state.clock.elapsedTime * 3) * 0.05;
        ringRef.current.scale.set(scale, scale, scale);
      }
    }
  });

  const getColor = () => {
    switch (status) {
      case "running":
        return "#8b5cf6";
      case "completed":
        return "#10b981";
      case "failed":
        return "#f87171";
      default:
        return "#52525b";
    }
  };

  return (
    <group position={position}>
      {/* Outer translucent orb - glass morphism */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[1.5, 32, 32]} />
        <meshPhysicalMaterial
          color={getColor()}
          transmission={0.2}
          thickness={0.5}
          roughness={0.2}
          metalness={0.1}
          clearcoat={1}
          clearcoatRoughness={0.1}
          transparent
          opacity={0.6}
          emissive={getColor()}
          emissiveIntensity={0.2}
        />
      </mesh>

      {/* Inner core */}
      <mesh ref={innerRef}>
        <icosahedronGeometry args={[0.8, 1]} />
        <meshStandardMaterial color={getColor()} emissive={getColor()} emissiveIntensity={0.5} wireframe={false} />
      </mesh>

      {/* Status ring */}
      <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.8, 0.02, 16, 100]} />
        <meshStandardMaterial color={getColor()} emissive={getColor()} emissiveIntensity={0.8} transparent opacity={0.6} />
      </mesh>

      {/* Abstract memory activity indicator - subtle pulse, not raw DB nodes */}
      {hasMemoryActivity && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[2.0, 2.05, 64]} />
          <meshBasicMaterial color="#8b5cf6" transparent opacity={0.15} side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  );
}
