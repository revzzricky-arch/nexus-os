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
import { useRuntimeStore } from "@/lib/store/runtime";

interface SceneProps {
  selectedAgent: string | null;
  onSelectAgent: (id: string | null) => void;
  selectedTask: string | null;
  onSelectTask: (id: string | null) => void;
  selectedApproval: string | null;
  onSelectApproval: (id: string | null) => void;
}

function SceneContent({ selectedAgent, onSelectAgent, selectedTask, onSelectTask, selectedApproval, onSelectApproval }: SceneProps) {
  const groupRef = useRef<THREE.Group>(null);
  const [time, setTime] = useState(0);
  const agents = useRuntimeStore((s) => s.agents);
  const tasks = useRuntimeStore((s) => s.tasks);
  const approvals = useRuntimeStore((s) => s.approvals);
  const activeMission = useRuntimeStore((s) => s.activeMission);

  useFrame((_, delta) => {
    setTime((t) => t + delta);
  });

  // Hybrid orbital agents - runtime focus, not memory DB
  const agentPositions = useMemo(() => {
    return agents.map((agent, idx) => {
      const total = agents.length;
      const baseAngle = (idx / total) * Math.PI * 2;
      // Restrained orbital radius, not oversized
      const orbitRadius = 2.8 + idx * 0.3;
      // Status-based orbit speed: RUNNING active, IDLE static, PAUSED dimmed etc.
      let orbitSpeed = 0.05;
      if (agent.state === "RUNNING") orbitSpeed = 0.35;
      else if (agent.state === "PLANNING") orbitSpeed = 0.15;
      else if (agent.state === "WAITING") orbitSpeed = 0.08;
      else if (agent.state === "WAITING_FOR_APPROVAL") orbitSpeed = 0.02;
      else if (agent.state === "IDLE") orbitSpeed = 0.03;
      else if (agent.state === "COMPLETED") orbitSpeed = 0.01;
      else if (agent.state === "FAILED") orbitSpeed = 0;
      else if (agent.state === "PAUSED") orbitSpeed = 0;

      const angle = baseAngle + time * orbitSpeed;
      const x = Math.cos(angle) * orbitRadius;
      const z = Math.sin(angle) * orbitRadius;
      // Subtle vertical bob, restrained
      const y = 0.4 + Math.sin(time * 0.5 + idx) * 0.15;
      return { ...agent, position: [x, y, z] as [number, number, number], orbitRadius };
    });
  }, [agents, time]);

  // Layered DAG tasks around core
  const taskPositions = useMemo(() => {
    return tasks.map((task, idx) => {
      const layer = task.layer;
      // Spread across 120 degrees for readability
      const angle = (idx / Math.max(tasks.length, 1)) * Math.PI * 0.8 - Math.PI * 0.4;
      const radius = 5.5 + layer * 1.8;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      const y = -0.2 + layer * 0.15;
      return { ...task, position: [x, y, z] as [number, number, number] };
    });
  }, [tasks]);

  // Workflow edges: task dependencies + agent->task
  const edges = useMemo(() => {
    const e: { from: string; to: string; status: string }[] = [];
    // Task DAG dependencies
    tasks.forEach((t) => {
      t.dependencies.forEach((dep) => {
        e.push({ from: dep, to: t.id, status: t.status });
      });
    });
    // Agent to current task
    agents.forEach((a) => {
      if (a.current_task_id) {
        e.push({ from: a.id, to: a.current_task_id, status: a.state });
      }
    });
    return e;
  }, [tasks, agents]);

  // Approval gates positioned mid-edge for pending approvals
  const pendingApprovals = approvals.filter((a) => a.status === "PENDING");

  const approvalGatePositions = useMemo(() => {
    return pendingApprovals.map((approval, idx) => {
      // Find positions of from/to if possible, otherwise distribute
      const task = taskPositions.find((t) => t.id === approval.task_id);
      const agent = agentPositions.find((ag) => ag.id === approval.agent_id);
      if (task && agent) {
        const midX = (task.position[0] + agent.position[0]) / 2;
        const midY = (task.position[1] + agent.position[1]) / 2 + 0.5;
        const midZ = (task.position[2] + agent.position[2]) / 2;
        return { approval, position: [midX, midY, midZ] as [number, number, number] };
      }
      // Fallback radial
      const angle = (idx / pendingApprovals.length) * Math.PI * 2;
      const r = 4.5;
      return { approval, position: [Math.cos(angle) * r, 0.8, Math.sin(angle) * r] as [number, number, number] };
    });
  }, [pendingApprovals, taskPositions, agentPositions]);

  return (
    <>
      {/* Lighting - subtle, not gaming neon, restrained */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 8, 5]} intensity={0.7} color="#ffffff" />
      <pointLight position={[0, 2, 0]} intensity={0.4} color="#8b5cf6" distance={12} decay={2} />
      <pointLight position={[-3, 1, -2]} intensity={0.2} color="#06b6d4" distance={8} />

      <fogExp2 attach="fog" args={["#09090b", 0.018]} />

      <group ref={groupRef}>
        {/* Mission Core - central geometry subtle rotation status ring activity pulse memory indicator not oversized */}
        <MissionCore
          position={[0, 0.3, 0]}
          status={activeMission?.status || "running"}
          progress={activeMission?.progress || 65}
          hasMemoryActivity={true}
        />

        {/* Agents - orbital, distinct visuals per state, restrained */}
        {agentPositions.map((agent) => (
          <AgentNode
            key={agent.id}
            id={agent.id}
            type={agent.type}
            state={agent.state}
            position={agent.position}
            isSelected={selectedAgent === agent.id}
            hasApproval={agent.state === "WAITING_FOR_APPROVAL"}
            onSelect={() => onSelectAgent(selectedAgent === agent.id ? null : agent.id)}
          />
        ))}

        {/* Tasks - layered DAG, concise labels, status */}
        {taskPositions.map((task) => (
          <TaskNode
            key={task.id}
            id={task.id}
            status={task.status}
            position={task.position}
            layer={task.layer}
            title={task.title}
            isSelected={selectedTask === task.id}
            onSelect={() => onSelectTask(selectedTask === task.id ? null : task.id)}
          />
        ))}

        {/* Workflow splines - elegant CatmullRom, active subtle movement, inactive subdued, no noise */}
        <WorkflowSplines agents={agentPositions} tasks={taskPositions} edges={edges} />

        {/* Approval gates - hexagonal, click opens 2D approval UI */}
        {approvalGatePositions.map(({ approval, position }) => (
          <ApprovalGate
            key={approval.id}
            id={approval.id}
            position={position}
            status={approval.status}
            isSelected={selectedApproval === approval.id}
            onClick={() => onSelectApproval(selectedApproval === approval.id ? null : approval.id)}
          />
        ))}

        {/* Event particles - minimal handoff/tool/memory/completion */}
        <EventParticles agents={agentPositions} />
      </group>

      {/* Ground grid - subtle */}
      <Grid
        position={[0, -0.6, 0]}
        args={[100, 100]}
        cellSize={0.8}
        cellThickness={0.25}
        cellColor="#27272a"
        sectionSize={4}
        sectionThickness={0.4}
        sectionColor="#3f3f46"
        fadeDistance={28}
        fadeStrength={1.2}
        followCamera={false}
        infiniteGrid={true}
      />
    </>
  );
}

export default function MissionCanvas(props: SceneProps) {
  const [hasError, setHasError] = useState(false);

  if (hasError) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-zinc-900/50 rounded-xl border border-zinc-800">
        <div className="text-center space-y-2 p-6">
          <p className="text-sm text-zinc-400">3D failed to mount</p>
          <p className="text-xs text-zinc-600 max-w-[280px]">Showing 2D fallback per architecture — mission runtime data available in panels</p>
          <button
            onClick={() => setHasError(false)}
            className="text-xs px-3 py-1.5 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-400 transition-colors"
          >
            Retry WebGL
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-[#09090b] relative overflow-hidden rounded-xl">
      <Canvas
        dpr={[1, 2]}
        gl={{ antialias: true, powerPreference: "high-performance", alpha: false }}
        shadows={false}
        onCreated={({ gl }) => {
          gl.setClearColor("#09090b");
        }}
        onError={() => setHasError(true)}
      >
        <PerspectiveCamera makeDefault position={[0, 7, 13]} fov={45} near={0.1} far={1000} />
        <SceneContent {...props} />
        <OrbitControls
          enableDamping
          dampingFactor={0.06}
          rotateSpeed={0.45}
          zoomSpeed={0.9}
          panSpeed={0.4}
          minDistance={4}
          maxDistance={28}
          maxPolarAngle={Math.PI / 2.15}
          minPolarAngle={0.15}
          target={[0, 0, 0]}
        />
        {/* Environment - soft, not gaming */}
        <Environment preset="city" />
      </Canvas>

      {/* Overlay info */}
      <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none">
        <div className="px-2.5 py-1 rounded-full bg-zinc-900/80 backdrop-blur border border-zinc-800 text-[10px] text-zinc-500 font-mono">
          Hybrid Orbital + Layered DAG • Runtime Focus
        </div>
        <div className="px-2.5 py-1 rounded-full bg-zinc-900/80 backdrop-blur border border-zinc-800 text-[10px] text-zinc-500 font-mono">
          WebGL2 • R3F 9 • Damping • Limits
        </div>
      </div>

      {/* Controls hint */}
      <div className="absolute bottom-3 left-3 px-2.5 py-1 rounded-full bg-zinc-900/70 backdrop-blur border border-zinc-800 text-[10px] text-zinc-600 pointer-events-none">
        Orbit • Zoom • Pan • Click agent/task/approval
      </div>
    </div>
  );
}
