"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface ApprovalGateProps {
  id?: string;
  position: [number, number, number];
  status: string;
  isSelected?: boolean;
  onClick: () => void;
}

export function ApprovalGate({ position, status, isSelected, onClick }: ApprovalGateProps) {
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state, delta) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime;
    if (status === "PENDING") {
      // Subtle rotation pulse for pending
      if (meshRef.current) {
        meshRef.current.rotation.y += delta * 0.6;
        const s = 1 + Math.sin(t * 2) * 0.08;
        meshRef.current.scale.setScalar(s);
      }
    }
  });

  const visuals = useMemo(() => {
    let color = "#71717a";
    let emissive = "#71717a";
    let intensity = 0.1;
    let opacity = 0.7;

    switch (status) {
      case "PENDING":
        color = "#f59e0b";
        emissive = "#f59e0b";
        intensity = 0.5;
        break;
      case "APPROVED":
        color = "#10b981";
        emissive = "#10b981";
        intensity = 0.2;
        break;
      case "DENIED":
        color = "#ef4444";
        emissive = "#ef4444";
        intensity = 0.2;
        break;
      case "EXPIRED":
        color = "#52525b";
        emissive = "#52525b";
        intensity = 0.05;
        opacity = 0.4;
        break;
    }

    if (isSelected) {
      intensity = Math.max(intensity, 0.7);
    }

    return { color, emissive, intensity, opacity };
  }, [status, isSelected]);

  return (
    <group position={position} ref={groupRef}>
      {/* Hexagonal torus - distinctive gate shape */}
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        onPointerOver={() => {
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "auto";
        }}
      >
        <torusGeometry args={[0.28, 0.04, 6, 6]} />
        <meshStandardMaterial
          color={visuals.color}
          emissive={visuals.emissive}
          emissiveIntensity={visuals.intensity}
          transparent
          opacity={visuals.opacity}
          roughness={0.4}
          metalness={0.3}
        />
      </mesh>

      {/* Inner hex */}
      <mesh rotation={[0, 0, Math.PI / 6]}>
        <torusGeometry args={[0.15, 0.015, 6, 6]} />
        <meshStandardMaterial color={visuals.color} transparent opacity={0.4} emissive={visuals.emissive} emissiveIntensity={0.2} />
      </mesh>

      {/* Selection highlight */}
      {isSelected && (
        <mesh>
          <torusGeometry args={[0.38, 0.02, 6, 6]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.2} />
        </mesh>
      )}

      {/* Status indicator dot */}
      {status === "PENDING" && (
        <mesh position={[0, 0.35, 0]}>
          <sphereGeometry args={[0.05, 8, 8]} />
          <meshStandardMaterial color="#f59e0b" emissive="#f59e0b" emissiveIntensity={0.8} />
        </mesh>
      )}
    </group>
  );
}
