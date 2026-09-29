"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface EventParticlesProps {
  agents: Array<{ id: string; position: [number, number, number]; status: string }>;
}

export function EventParticles({ agents }: EventParticlesProps) {
  const pointsRef = useRef<THREE.Points>(null);

  const particles = useMemo(() => {
    // Create 30 particles for tool activity visualization - runtime only
    const count = 30;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      // Random around agents
      const agent = agents[i % agents.length];
      if (agent) {
        positions[i * 3] = agent.position[0] + (Math.random() - 0.5) * 2;
        positions[i * 3 + 1] = agent.position[1] + Math.random() * 2;
        positions[i * 3 + 2] = agent.position[2] + (Math.random() - 0.5) * 2;

        // Color based on tool activity
        const isActive = agent.status === "tool_calling" || agent.status === "running";
        if (isActive) {
          colors[i * 3] = 0.5; // R
          colors[i * 3 + 1] = 0.4; // G - violet
          colors[i * 3 + 2] = 1.0; // B
        } else {
          colors[i * 3] = 0.3;
          colors[i * 3 + 1] = 0.3;
          colors[i * 3 + 2] = 0.3;
        }
      }
    }

    return { positions, colors, count };
  }, [agents]);

  useFrame((state, delta) => {
    if (pointsRef.current) {
      const positions = pointsRef.current.geometry.attributes.position.array as Float32Array;
      // Simple upward drift for tool activity
      for (let i = 0; i < particles.count; i++) {
        positions[i * 3 + 1] += delta * 0.5;
        if (positions[i * 3 + 1] > 5) {
          positions[i * 3 + 1] = 0;
        }
      }
      pointsRef.current.geometry.attributes.position.needsUpdate = true;
      pointsRef.current.rotation.y += delta * 0.05;
    }
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={particles.count}
          array={particles.positions}
          itemSize={3}
          args={[particles.positions, 3]}
        />
        <bufferAttribute
          attach="attributes-color"
          count={particles.count}
          array={particles.colors}
          itemSize={3}
          args={[particles.colors, 3]}
        />
      </bufferGeometry>
      <pointsMaterial size={0.08} vertexColors transparent opacity={0.6} sizeAttenuation />
    </points>
  );
}
