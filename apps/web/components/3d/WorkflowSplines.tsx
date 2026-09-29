"use client";

import { useMemo } from "react";
import * as THREE from "three";
import { Line } from "@react-three/drei";

interface Edge {
  from: string;
  to: string;
  status: string;
}

interface WorkflowSplinesProps {
  agents: Array<{ id: string; position: [number, number, number] }>;
  tasks: Array<{ id: string; position: [number, number, number] }>;
  edges: Edge[];
}

export function WorkflowSplines({ agents, tasks, edges }: WorkflowSplinesProps) {
  const allNodes = useMemo(() => {
    const map = new Map<string, [number, number, number]>();
    agents.forEach((a) => map.set(a.id, a.position));
    tasks.forEach((t) => map.set(t.id, t.position));
    return map;
  }, [agents, tasks]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "#8b5cf6";
      case "completed":
        return "#10b981";
      case "failed":
        return "#ef4444";
      default:
        return "#27272a";
    }
  };

  return (
    <group>
      {edges.map((edge, idx) => {
        const fromPos = allNodes.get(edge.from);
        const toPos = allNodes.get(edge.to);
        if (!fromPos || !toPos) return null;

        // Create curved path
        const mid: [number, number, number] = [
          (fromPos[0] + toPos[0]) / 2,
          (fromPos[1] + toPos[1]) / 2 + 1,
          (fromPos[2] + toPos[2]) / 2,
        ];

        const points = [
          new THREE.Vector3(...fromPos),
          new THREE.Vector3(...mid),
          new THREE.Vector3(...toPos),
        ];

        const curve = new THREE.CatmullRomCurve3(points);
        const curvePoints = curve.getPoints(20);

        return (
          <group key={idx}>
            <Line
              points={curvePoints}
              color={getStatusColor(edge.status)}
              lineWidth={edge.status === "running" ? 2 : 1}
              transparent
              opacity={edge.status === "running" ? 0.8 : 0.4}
            />
            {/* Arrow head at target */}
            <mesh position={toPos}>
              <coneGeometry args={[0.05, 0.15, 8]} />
              <meshBasicMaterial color={getStatusColor(edge.status)} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}
