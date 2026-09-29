"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface Positioned {
  id: string;
  position: [number, number, number];
}

interface Edge {
  from: string;
  to: string;
  status: string;
}

interface WorkflowSplinesProps {
  agents: Positioned[];
  tasks: Positioned[];
  edges: Edge[];
}

export function WorkflowSplines({ agents, tasks, edges }: WorkflowSplinesProps) {
  const allNodes = useMemo(() => [...agents, ...tasks], [agents, tasks]);

  return (
    <group>
      {edges.map((edge, idx) => {
        const fromNode = allNodes.find((n) => n.id === edge.from);
        const toNode = allNodes.find((n) => n.id === edge.to);
        if (!fromNode || !toNode) return null;
        return <SplineEdge key={`${edge.from}-${edge.to}-${idx}`} from={fromNode.position} to={toNode.position} status={edge.status} />;
      })}
    </group>
  );
}

function SplineEdge({ from, to, status }: { from: [number, number, number]; to: [number, number, number]; status: string }) {
  const lineRef = useRef<THREE.Line>(null);
  const coneRef = useRef<THREE.Mesh>(null);

  const { curve, color, opacity, isActive } = useMemo(() => {
    const start = new THREE.Vector3(...from);
    const end = new THREE.Vector3(...to);
    const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
    // Elegant arc
    mid.y += 0.6;

    const curve = new THREE.CatmullRomCurve3([start, mid, end]);
    curve.curveType = "centripetal";

    let c = "#27272a";
    let o = 0.25;
    let active = false;

    if (status === "RUNNING" || status === "running") {
      c = "#8b5cf6";
      o = 0.6;
      active = true;
    } else if (status === "COMPLETED" || status === "completed") {
      c = "#10b981";
      o = 0.35;
    } else if (status === "QUEUED" || status === "queued") {
      c = "#52525b";
      o = 0.25;
    } else if (status === "PENDING" || status === "pending") {
      c = "#27272a";
      o = 0.15;
    } else if (status === "FAILED" || status === "failed") {
      c = "#ef4444";
      o = 0.3;
    } else if (status === "BLOCKED" || status === "blocked") {
      c = "#f59e0b";
      o = 0.3;
    } else if (status === "WAITING_FOR_APPROVAL") {
      c = "#f59e0b";
      o = 0.5;
      active = true;
    }

    return { curve, color: c, opacity: o, isActive: active };
  }, [from, to, status]);

  const points = useMemo(() => curve.getPoints(32), [curve]);
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);

  useFrame((state) => {
    if (!isActive || !lineRef.current) return;
    const t = state.clock.elapsedTime;
    // Subtle movement for active - not noisy
    const mat = lineRef.current.material as THREE.LineDashedMaterial;
    if (mat && "dashOffset" in mat) {
      mat.dashOffset = -t * 0.5;
    }
  });

  const endDir = useMemo(() => {
    const tangent = curve.getTangent(0.9);
    return tangent;
  }, [curve]);

  const endPos = useMemo(() => curve.getPoint(0.92), [curve]);

  return (
    <group>
      <primitive
        object={
          new THREE.Line(
            geometry,
            new THREE.LineDashedMaterial({
              color,
              transparent: true,
              opacity,
              linewidth: 1,
              dashSize: isActive ? 0.2 : 0,
              gapSize: isActive ? 0.15 : 0,
            })
          )
        }
        ref={lineRef}
      />

      {/* Arrow cone for direction - subtle */}
      <mesh position={endPos} ref={coneRef} quaternion={new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), endDir)}>
        <coneGeometry args={[0.06, 0.14, 6]} />
        <meshStandardMaterial color={color} transparent opacity={opacity} emissive={color} emissiveIntensity={isActive ? 0.3 : 0.05} />
      </mesh>
    </group>
  );
}
