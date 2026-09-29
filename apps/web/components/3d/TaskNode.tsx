"use client";

import { useRef, useState } from "react";
import { Html } from "@react-three/drei";
import * as THREE from "three";

interface TaskNodeProps {
  id: string;
  status: string;
  position: [number, number, number];
  layer: number;
  title: string;
}

export function TaskNode({ id, status, position, layer, title }: TaskNodeProps) {
  const [hovered, setHovered] = useState(false);

  const getColor = () => {
    switch (status) {
      case "running":
        return "#8b5cf6";
      case "completed":
        return "#10b981";
      case "failed":
        return "#ef4444";
      case "queued":
        return "#52525b";
      default:
        return "#27272a";
    }
  };

  return (
    <group position={position}>
      <mesh
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHovered(false);
          document.body.style.cursor = "default";
        }}
        scale={hovered ? 1.1 : 1}
      >
        <boxGeometry args={[0.5, 0.15, 0.5]} />
        <meshStandardMaterial
          color={getColor()}
          emissive={getColor()}
          emissiveIntensity={status === "running" ? 0.6 : 0.2}
          metalness={0.1}
          roughness={0.4}
        />
      </mesh>

      {/* Layer indicator - small pillar height = layer */}
      <mesh position={[0, layer * 0.1, 0]}>
        <cylinderGeometry args={[0.02, 0.02, layer * 0.2, 8]} />
        <meshStandardMaterial color="#3f3f46" />
      </mesh>

      {hovered && (
        <Html distanceFactor={10} position={[0, 0.5, 0]} center>
          <div className="px-2 py-1 rounded-lg bg-zinc-900/90 backdrop-blur border border-zinc-800 text-[11px] text-zinc-200 whitespace-nowrap pointer-events-none">
            <div className="font-medium">{title}</div>
            <div className="text-[10px] text-zinc-500">
              {id} • layer {layer} • {status}
            </div>
          </div>
        </Html>
      )}
    </group>
  );
}
