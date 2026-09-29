"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, PerspectiveCamera, Grid, Environment } from "@react-three/drei";
import { useRef, useMemo, useState } from "react";
import * as THREE from "three";
import { AgentNode } from "./AgentNode";
import { MissionCore } from "./MissionCore";
import { TaskNode } from "./TaskNode";
import { WorkflowSplines } from "./WorkflowSplines";
import { ApprovalGate } from "./ApprovalGate";
import { EventParticles } from "./EventParticles";

interface SceneProps {
  selectedAgent: string | null;
  onSelectAgent: (id: string | null) => void;
}

// Mock runtime state - scaffold only, 3 placeholder agents, simple task nodes
const AGENTS = [
  { id: "researcher-1", type: "researcher", status: "running", orbitIndex: 0, hasApproval: false },
  { id: "coder-1", type: "coder", status: "tool_calling", orbitIndex: 1, hasApproval: true },
  { id: "analyst-1", type: "analyst", status: "queued", orbitIndex: 2, hasApproval: false },
];

const TASKS = [
  { id: "task-1", title: "Research", status: "running", layer: 0, dependencies: [] },
  { id: "task-2", title: "Analyze", status: "queued", layer: 1, dependencies: ["task-1"] },
  { id: "task-3", title: "Write", status: "pending", layer: 2, dependencies: ["task-2"] },
];

function SceneContent({ selectedAgent, onSelectAgent }: SceneProps) {
  const groupRef = useRef<THREE.Group>(null);
  const [time, setTime] = useState(0);

  useFrame((state, delta) => {
    setTime((t) => t + delta);
    if (groupRef.current) {
      // Subtle slow rotation for orbital feel when idle
      // groupRef.current.rotation.y += delta * 0.02;
    }
  });

  // Calculate agent positions - hybrid orbital
  const agentPositions = useMemo(() => {
    return AGENTS.map((agent, idx) => {
      const total = AGENTS.length;
      const baseAngle = (idx / total) * Math.PI * 2;
      const orbitRadius = 3 + idx * 0.2;
      const orbitSpeed = agent.status === "running" ? 0.5 : agent.status === "tool_calling" ? 0.8 : 0.1;
      const angle = baseAngle + time * orbitSpeed;
      const x = Math.cos(angle) * orbitRadius;
      const z = Math.sin(angle) * orbitRadius;
      const y = 0.5 + Math.sin(time + idx) * 0.2;
      return { ...agent, position: [x, y, z] as [number, number, number], orbitRadius };
    });
  }, [time]);

  // Calculate task positions - layered DAG
  const taskPositions = useMemo(() => {
    return TASKS.map((task, idx) => {
      const layer = task.layer;
      const angle = (idx / TASKS.length) * Math.PI * 0.5 - Math.PI * 0.25; // spread 90 deg
      const radius = 6 + layer * 1.5;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      const y = 0;
      return { ...task, position: [x, y, z] as [number, number, number] };
    });
  }, []);

  return (
    <>
      {/* Lighting - subtle, not gaming */}
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 10, 5]} intensity={0.8} />
      <pointLight position={[0, 3, 0]} intensity={0.5} color="#8b5cf6" />

      {/* Fog for depth */}
      <fogExp2 attach="fog" args={["#09090b", 0.02]} />

      <group ref={groupRef}>
        {/* Mission Core - central orb */}
        <MissionCore position={[0, 0.5, 0]} status="running" hasMemoryActivity={true} />

        {/* Agents - inner orbit runtime focus */}
        {agentPositions.map((agent) => (
          <AgentNode
            key={agent.id}
            id={agent.id}
            type={agent.type}
            status={agent.status}
            position={agent.position}
            isSelected={selectedAgent === agent.id}
            hasApproval={agent.hasApproval}
            onSelect={() => onSelectAgent(selectedAgent === agent.id ? null : agent.id)}
          />
        ))}

        {/* Tasks - layered DAG */}
        {taskPositions.map((task) => (
          <TaskNode
            key={task.id}
            id={task.id}
            status={task.status}
            position={task.position}
            layer={task.layer}
            title={task.title}
          />
        ))}

        {/* Workflow splines - subtle connections */}
        <WorkflowSplines
          agents={agentPositions}
          tasks={taskPositions}
          edges={[
            { from: "task-1", to: "task-2", status: "running" },
            { from: "task-2", to: "task-3", status: "pending" },
            { from: "researcher-1", to: "task-1", status: "running" },
            { from: "coder-1", to: "task-3", status: "pending" },
          ]}
        />

        {/* Approval gate - on edge task-2 -> task-3 */}
        <ApprovalGate
          position={[7.5, 0, 0.5]}
          status="pending"
          onClick={() => console.log("Approval gate clicked - scaffold")}
        />

        {/* Event particles - tool activity runtime only */}
        <EventParticles agents={agentPositions} />
      </group>

      {/* Ground grid - subtle */}
      <Grid
        position={[0, -0.5, 0]}
        args={[100, 100]}
        cellSize={1}
        cellThickness={0.3}
        cellColor="#27272a"
        sectionSize={5}
        sectionThickness={0.5}
        sectionColor="#27272a"
        fadeDistance={30}
        fadeStrength={1}
        followCamera={false}
        infiniteGrid={true}
      />
    </>
  );
}

export default function MissionCanvas({ selectedAgent, onSelectAgent }: SceneProps) {
  const [hasError, setHasError] = useState(false);

  if (hasError) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-zinc-900/50 rounded-xl border border-zinc-800">
        <div className="text-center space-y-2">
          <p className="text-sm text-zinc-400">3D failed to mount</p>
          <p className="text-xs text-zinc-600">Showing 2D fallback per architecture</p>
          <button
            onClick={() => setHasError(false)}
            className="text-xs px-3 py-1 rounded-full bg-zinc-800 text-zinc-400"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-[#09090b] relative">
      <Canvas
        dpr={[1, 2]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        shadows={false}
        onCreated={({ gl }) => {
          gl.setClearColor("#09090b");
        }}
        onError={() => setHasError(true)}
      >
        <PerspectiveCamera makeDefault position={[0, 8, 15]} fov={50} near={0.1} far={1000} />
        <SceneContent selectedAgent={selectedAgent} onSelectAgent={onSelectAgent} />
        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          rotateSpeed={0.5}
          zoomSpeed={1.0}
          panSpeed={0.5}
          minDistance={5}
          maxDistance={30}
          maxPolarAngle={Math.PI / 2.1}
          minPolarAngle={0.1}
        />
        {/* Environment - soft HDRI not gaming */}
        <Environment preset="city" />
      </Canvas>

      {/* Overlay for WebGL check */}
      <div className="absolute top-4 right-4 px-2.5 py-1 rounded-full bg-zinc-900/80 backdrop-blur border border-zinc-800 text-[10px] text-zinc-500 pointer-events-none">
        WebGL2 • R3F 9 • Drei • Runtime Focus
      </div>
    </div>
  );
}
