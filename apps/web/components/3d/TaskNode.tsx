"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { Text } from "@react-three/drei";

interface TaskNodeProps {
  id: string;
  status: string;
  position: [number, number, number];
  layer: number;
  title: string;
  isSelected?: boolean;
  onSelect?: () => void;
}

export function TaskNode({ id, status, position, layer, title, isSelected, onSelect }: TaskNodeProps) {
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state, delta) => {
    if (!meshRef.current) return;
    const t = state.clock.elapsedTime;
    if (status === "RUNNING") {
      meshRef.current.rotation.y += delta * 0.8;
      const s = 1 + Math.sin(t * 2) * 0.05;
      meshRef.current.scale.setScalar(s);
    } else if (status === "QUEUED") {
      meshRef.current.rotation.y += delta * 0.15;
    }
  });

  const visuals = useMemo(() => {
    let color = "#27272a";
    let emissive = "#27272a";
    let emissiveIntensity = 0.05;
    let opacity = 0.9;

    switch (status) {
      case "PENDING":
        color = "#27272a";
        emissive = "#52525b";
        emissiveIntensity = 0.05;
        opacity = 0.6;
        break;
      case "QUEUED":
        color = "#3f3f46";
        emissive = "#71717a";
        emissiveIntensity = 0.1;
        break;
      case "RUNNING":
        color = "#8b5cf6";
        emissive = "#8b5cf6";
        emissiveIntensity = 0.35;
        break;
      case "COMPLETED":
        color = "#10b981";
        emissive = "#10b981";
        emissiveIntensity = 0.15;
        break;
      case "FAILED":
        color = "#ef4444";
        emissive = "#ef4444";
        emissiveIntensity = 0.25;
        break;
      case "BLOCKED":
        color = "#f59e0b";
        emissive = "#f59e0b";
        emissiveIntensity = 0.2;
        break;
    }

    if (isSelected) {
      emissiveIntensity = Math.max(emissiveIntensity, 0.5);
      opacity = 1;
    }

    return { color, emissive, emissiveIntensity, opacity };
  }, [status, isSelected]);

  return (
    <group position={position} ref={groupRef}>
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation();
          onSelect?.();
        }}
        onPointerOver={() => {
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "auto";
        }}
      >
        <boxGeometry args={[0.6, 0.22, 0.32]} />
        <meshStandardMaterial
          color={visuals.color}
          emissive={visuals.emissive}
          emissiveIntensity={visuals.emissiveIntensity}
          transparent
          opacity={visuals.opacity}
          roughness={0.5}
          metalness={0.2}
        />
      </mesh>

      {/* Layer indicator small */}
      <mesh position={[0, 0.2, 0]}>
        <sphereGeometry args={[0.04, 8, 8]} />
        <meshStandardMaterial color="#52525b" transparent opacity={0.5} />
      </mesh>

      {/* Title label - concise, clickable */}
      <Text
        position={[0, -0.35, 0]}
        fontSize={0.18}
        color={isSelected ? "#ffffff" : "#a1a1aa"}
        anchorX="center"
        anchorY="middle"
        maxWidth={2}
        lineHeight={1}
        font="/fonts/GeistMono-Regular.woff"
        // fallback if font missing
      >
        {title}
      </Text>

      {/* Status dot */}
      <mesh position={[0.32, 0, 0]}>
        <sphereGeometry args={[0.04, 8, 8]} />
        <meshStandardMaterial color={visuals.emissive} emissive={visuals.emissive} emissiveIntensity={0.8} />
      </mesh>

      {isSelected && (
        <mesh position={[0, 0, 0]}>
          <boxGeometry args={[0.66, 0.28, 0.38]} />
          <meshBasicMaterial color="#ffffff" wireframe transparent opacity={0.15} />
        </mesh>
      )}
    </group>
  );
}
