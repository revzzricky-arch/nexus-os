"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface Positioned {
  id: string;
  position: [number, number, number];
}

interface EventParticlesProps {
  agents: Positioned[];
}

export function EventParticles({ agents }: EventParticlesProps) {
  const pointsRef = useRef<THREE.Points>(null);

  // Minimal particles for handoff tool call memory retrieval completion - restrained
  const { positions, colors } = useMemo(() => {
    const count = 30;
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      // Distribute around agents
      const agent = agents[i % agents.length];
      if (agent) {
        pos[i * 3] = agent.position[0] + (Math.random() - 0.5) * 0.5;
        pos[i * 3 + 1] = agent.position[1] + Math.random() * 1.5;
        pos[i * 3 + 2] = agent.position[2] + (Math.random() - 0.5) * 0.5;
      } else {
        pos[i * 3] = (Math.random() - 0.5) * 6;
        pos[i * 3 + 1] = Math.random() * 2;
        pos[i * 3 + 2] = (Math.random() - 0.5) * 6;
      }

      // Color by type - subtle violet/cyan/amber/emerald
      const type = i % 4;
      if (type === 0) {
        // tool call violet
        col[i * 3] = 0.55;
        col[i * 3 + 1] = 0.36;
        col[i * 3 + 2] = 0.96;
      } else if (type === 1) {
        // memory cyan
        col[i * 3] = 0.02;
        col[i * 3 + 1] = 0.71;
        col[i * 3 + 2] = 0.83;
      } else if (type === 2) {
        // handoff amber
        col[i * 3] = 0.96;
        col[i * 3 + 1] = 0.62;
        col[i * 3 + 2] = 0.04;
      } else {
        // completion emerald
        col[i * 3] = 0.06;
        col[i * 3 + 1] = 0.72;
        col[i * 3 + 2] = 0.51;
      }
    }

    return { positions: pos, colors: col };
  }, [agents]);

  useFrame((state, delta) => {
    if (!pointsRef.current) return;
    const positions = pointsRef.current.geometry.attributes.position as THREE.BufferAttribute;
    // Upward drift minimal
    for (let i = 0; i < positions.count; i++) {
      positions.setY(i, positions.getY(i) + delta * 0.15);
      if (positions.getY(i) > 3) {
        positions.setY(i, -0.5);
      }
    }
    positions.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.06} vertexColors transparent opacity={0.5} sizeAttenuation />
    </points>
  );
}
