"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

interface OrbitConfig {
  baseAngle: number;
  orbitRadius: number;
  orbitSpeed: number;
  orbitIndex: number;
}

interface AgentNodeProps {
  id: string;
  type: string;
  state: string;
  isSelected: boolean;
  hasApproval: boolean;
  onSelect: () => void;
  orbitConfig: OrbitConfig;
}

export function AgentNode({ id, type, state, isSelected, hasApproval, onSelect, orbitConfig }: AgentNodeProps) {
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh>(null);
  const pulseRef = useRef<THREE.Mesh>(null);

  // Use refs and R3F clock directly for per-frame animation, no React setState
  useFrame((stateClock, delta) => {
    const t = stateClock.clock.elapsedTime;
    if (!groupRef.current) return;

    // Orbital motion - computed from clock directly, not React state
    const angle = orbitConfig.baseAngle + t * orbitConfig.orbitSpeed;
    const x = Math.cos(angle) * orbitConfig.orbitRadius;
    const z = Math.sin(angle) * orbitConfig.orbitRadius;
    const y = 0.4 + Math.sin(t * 0.5 + orbitConfig.orbitIndex) * 0.15;
    groupRef.current.position.set(x, y, z);

    // Status-based animation: restrained, no extreme emissive
    if (state === "RUNNING") {
      const s = 1 + Math.sin(t * 3) * 0.08;
      if (meshRef.current) meshRef.current.scale.setScalar(s);
      if (pulseRef.current) {
        pulseRef.current.scale.setScalar(1 + Math.sin(t * 2) * 0.15);
        (pulseRef.current.material as THREE.MeshBasicMaterial).opacity = 0.08 + Math.sin(t * 2) * 0.03;
      }
    } else if (state === "PLANNING") {
      const s = 1 + Math.sin(t * 1.2) * 0.05;
      if (meshRef.current) meshRef.current.scale.setScalar(s);
    } else if (state === "WAITING") {
      if (meshRef.current) meshRef.current.scale.setScalar(0.9);
    } else if (state === "WAITING_FOR_APPROVAL") {
      const s = 1 + Math.sin(t * 2.5) * 0.1;
      if (meshRef.current) meshRef.current.scale.setScalar(s);
    } else if (state === "COMPLETED") {
      if (meshRef.current) meshRef.current.scale.setScalar(0.95);
    } else if (state === "FAILED") {
      if (meshRef.current) meshRef.current.rotation.z = Math.sin(t * 5) * 0.05;
    } else if (state === "PAUSED") {
      if (meshRef.current) meshRef.current.scale.setScalar(0.85);
    } else {
      if (meshRef.current) meshRef.current.scale.setScalar(1);
    }

    if (isSelected && groupRef.current) {
      groupRef.current.rotation.y += delta * 0.5;
    }
  });

  const visuals = useMemo(() => {
    let color = "#71717a";
    let emissive = "#71717a";
    let emissiveIntensity = 0.1;
    let geometry: THREE.BufferGeometry = new THREE.OctahedronGeometry(0.28, 0);

    if (type === "supervisor") {
      geometry = new THREE.OctahedronGeometry(0.32, 0);
      color = "#8b5cf6";
      emissive = "#8b5cf6";
    } else if (type === "researcher") {
      geometry = new THREE.IcosahedronGeometry(0.26, 0);
      color = "#06b6d4";
      emissive = "#06b6d4";
    } else if (type === "coder") {
      geometry = new THREE.BoxGeometry(0.42, 0.42, 0.42);
      color = "#f59e0b";
      emissive = "#f59e0b";
    } else if (type === "analyst") {
      geometry = new THREE.DodecahedronGeometry(0.28, 0);
      color = "#10b981";
      emissive = "#10b981";
    }

    switch (state) {
      case "IDLE":
        emissiveIntensity = 0.05;
        break;
      case "PLANNING":
        emissiveIntensity = 0.15;
        break;
      case "RUNNING":
        emissiveIntensity = 0.35;
        break;
      case "WAITING":
        emissiveIntensity = 0.08;
        color = "#52525b";
        break;
      case "WAITING_FOR_APPROVAL":
        emissiveIntensity = 0.5;
        color = "#f59e0b";
        emissive = "#f59e0b";
        break;
      case "COMPLETED":
        emissiveIntensity = 0.12;
        color = "#10b981";
        emissive = "#10b981";
        break;
      case "FAILED":
        emissiveIntensity = 0.3;
        color = "#ef4444";
        emissive = "#ef4444";
        break;
      case "PAUSED":
        emissiveIntensity = 0.03;
        color = "#3f3f46";
        break;
    }

    if (isSelected) {
      emissiveIntensity = Math.max(emissiveIntensity, 0.6);
    }

    return { color, emissive, emissiveIntensity, geometry };
  }, [type, state, isSelected]);

  // Initial static position for first frame before useFrame runs
  const initialPos = useMemo(() => {
    const x = Math.cos(orbitConfig.baseAngle) * orbitConfig.orbitRadius;
    const z = Math.sin(orbitConfig.baseAngle) * orbitConfig.orbitRadius;
    return [x, 0.4, z] as [number, number, number];
  }, [orbitConfig.baseAngle, orbitConfig.orbitRadius]);

  return (
    <group position={initialPos} ref={groupRef}>
      <mesh
        ref={meshRef}
        geometry={visuals.geometry}
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        onPointerOver={() => {
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "auto";
        }}
      >
        <meshStandardMaterial
          color={visuals.color}
          emissive={visuals.emissive}
          emissiveIntensity={visuals.emissiveIntensity}
          roughness={0.4}
          metalness={0.3}
        />
      </mesh>

      {isSelected && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.5, 0.02, 16, 32]} />
          <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={0.3} transparent opacity={0.6} />
        </mesh>
      )}

      <mesh ref={pulseRef}>
        <sphereGeometry args={[0.45, 16, 16]} />
        <meshBasicMaterial color={visuals.emissive} transparent opacity={state === "RUNNING" ? 0.08 : 0} />
      </mesh>

      {hasApproval && (
        <mesh position={[0, 0.5, 0]}>
          <octahedronGeometry args={[0.08, 0]} />
          <meshStandardMaterial color="#f59e0b" emissive="#f59e0b" emissiveIntensity={0.8} />
        </mesh>
      )}

      {state === "RUNNING" && (
        <mesh>
          <sphereGeometry args={[0.38, 12, 12]} />
          <meshBasicMaterial color={visuals.emissive} transparent opacity={0.04} wireframe />
        </mesh>
      )}
    </group>
  );
}
