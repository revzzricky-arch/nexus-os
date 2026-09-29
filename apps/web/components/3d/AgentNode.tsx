"use client";

import { useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";

interface AgentNodeProps {
  id: string;
  type: string;
  status: string;
  position: [number, number, number];
  isSelected: boolean;
  hasApproval: boolean;
  onSelect: () => void;
}

export function AgentNode({ id, type, status, position, isSelected, hasApproval, onSelect }: AgentNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  useFrame((state, delta) => {
    if (meshRef.current) {
      // Pulse based on status
      if (status === "running" || status === "tool_calling") {
        const pulse = 1 + Math.sin(state.clock.elapsedTime * (status === "tool_calling" ? 8 : 4)) * 0.1;
        meshRef.current.scale.set(pulse, pulse, pulse);
      }
      meshRef.current.rotation.y += delta * 0.5;
    }
  });

  const getColor = () => {
    switch (status) {
      case "running":
        return "#8b5cf6";
      case "tool_calling":
        return "#22d3ee";
      case "waiting_approval":
        return "#fbbf24";
      case "queued":
        return "#71717a";
      case "completed":
        return "#34d399";
      case "failed":
        return "#f87171";
      default:
        return "#52525b";
    }
  };

  const getGeometry = () => {
    // Different geometry per type but keep simple for MVP
    switch (type) {
      case "researcher":
        return <octahedronGeometry args={[0.4, 0]} />;
      case "coder":
        return <boxGeometry args={[0.6, 0.6, 0.6]} />;
      case "analyst":
        return <dodecahedronGeometry args={[0.4, 0]} />;
      default:
        return <icosahedronGeometry args={[0.4, 1]} />;
    }
  };

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHovered(false);
          document.body.style.cursor = "default";
        }}
        scale={isSelected ? 1.2 : hovered ? 1.1 : 1}
      >
        {getGeometry()}
        <meshStandardMaterial
          color={getColor()}
          emissive={getColor()}
          emissiveIntensity={isSelected ? 1.0 : hovered ? 0.8 : status === "running" || status === "tool_calling" ? 0.8 : 0.3}
          metalness={0.2}
          roughness={0.3}
          transparent
          opacity={isSelected ? 1 : 0.9}
        />
      </mesh>

      {/* Approval ring - amber when has approval */}
      {hasApproval && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.6, 0.03, 16, 32]} />
          <meshStandardMaterial color="#fbbf24" emissive="#fbbf24" emissiveIntensity={0.6} />
        </mesh>
      )}

      {/* Selection outline */}
      {isSelected && (
        <mesh>
          <icosahedronGeometry args={[0.55, 1]} />
          <meshBasicMaterial color="#8b5cf6" wireframe transparent opacity={0.2} />
        </mesh>
      )}

      {/* Tooltip on hover */}
      {hovered && (
        <Html distanceFactor={10} position={[0, 0.8, 0]} center>
          <div className="px-2.5 py-1.5 rounded-lg bg-zinc-900/90 backdrop-blur border border-zinc-800 text-xs text-zinc-200 whitespace-nowrap pointer-events-none">
            <div className="font-medium">{id}</div>
            <div className="text-[10px] text-zinc-500">
              {type} • {status} {hasApproval ? "• approval" : ""}
            </div>
          </div>
        </Html>
      )}
    </group>
  );
}
