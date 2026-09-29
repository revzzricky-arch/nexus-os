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

  // Stable seed - only recompute when agent count or ids change, not positions per-frame
  // This keeps geometry/data stable while only runtime positions update in useFrame
  const agentIdsKey = useMemo(() => agents.map((a) => a.id).join(","), [agents]);

  const { positions, colors } = useMemo(() => {
    const count = 30;
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
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

      const type = i % 4;
      if (type === 0) {
        col[i * 3] = 0.55;
        col[i * 3 + 1] = 0.36;
        col[i * 3 + 2] = 0.96;
      } else if (type === 1) {
        col[i * 3] = 0.02;
        col[i * 3 + 1] = 0.71;
        col[i * 3 + 2] = 0.83;
      } else if (type === 2) {
        col[i * 3] = 0.96;
        col[i * 3 + 1] = 0.62;
        col[i * 3 + 2] = 0.04;
      } else {
        col[i * 3] = 0.06;
        col[i * 3 + 1] = 0.72;
        col[i * 3 + 2] = 0.51;
      }
    }

    return { positions: pos, colors: col };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentIdsKey, agents.length]);

  useFrame((_, delta) => {
    if (!pointsRef.current) return;
    const posAttr = pointsRef.current.geometry.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < posAttr.count; i++) {
      posAttr.setY(i, posAttr.getY(i) + delta * 0.15);
      if (posAttr.getY(i) > 3) {
        posAttr.setY(i, -0.5);
      }
    }
    posAttr.needsUpdate = true;
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
