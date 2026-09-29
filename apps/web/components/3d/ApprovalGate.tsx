"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface ApprovalGateProps {
  position: [number, number, number];
  status: string;
  onClick?: () => void;
}

export function ApprovalGate({ position, status, onClick }: ApprovalGateProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.z += delta * 0.5;
      if (status === "pending") {
        const scale = 1 + Math.sin(state.clock.elapsedTime * 2) * 0.1;
        meshRef.current.scale.set(scale, scale, scale);
      }
    }
  });

  const getColor = () => {
    switch (status) {
      case "pending":
        return "#fbbf24";
      case "approved":
        return "#34d399";
      case "denied":
        return "#f87171";
      default:
        return "#52525b";
    }
  };

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        rotation={[Math.PI / 2, 0, 0]}
        onClick={(e) => {
          e.stopPropagation();
          onClick?.();
        }}
        onPointerOver={() => {
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "default";
        }}
      >
        <torusGeometry args={[0.5, 0.05, 6, 24]} />
        <meshStandardMaterial
          color={getColor()}
          emissive={getColor()}
          emissiveIntensity={0.6}
          transparent
          opacity={0.8}
        />
      </mesh>
      {/* Inner hex */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.3, 0.35, 6]} />
        <meshBasicMaterial color={getColor()} transparent opacity={0.3} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}
