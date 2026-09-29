import { UUID, ISODateTime, Timestamps, CostTracking } from "./common";

export type AgentType = "supervisor" | "researcher" | "coder" | "analyst" | "custom";

export type AgentState =
  | "idle"
  | "queued"
  | "planning"
  | "running"
  | "tool_calling"
  | "waiting_approval"
  | "waiting_dependency"
  | "completed"
  | "failed"
  | "cancelled";

export interface AgentConfig {
  id: UUID;
  type: AgentType;
  role: string;
  system_prompt_template: string;
  model_config: {
    provider: "openai-compatible" | "anthropic" | "ollama";
    model: string;
    temperature: number;
    max_tokens?: number;
    budget_tokens?: number;
  };
  tools: string[]; // tool ids allowed
  capability_tags: string[];
}

export interface AgentRun extends Timestamps, CostTracking {
  id: UUID;
  mission_id: UUID;
  task_id: UUID;
  agent_id: UUID;
  status: AgentState;
  messages: Array<{ role: string; content: string; timestamp: ISODateTime }>;
  started_at?: ISODateTime;
  completed_at?: ISODateTime;
}

// 3D state for agent nodes - runtime focus only
export interface Agent3DState {
  id: UUID;
  agent_type: AgentType;
  status: AgentState;
  position: [number, number, number]; // calculated from orbit index
  scale: number;
  color: string;
  emissiveIntensity: number;
  orbitSpeed: number; // 0 idle, >0 active
  orbitRadius: number; // inner orbit ~3 for agents
  orbitIndex: number;
  toolCallCount: number;
  hasApproval: boolean;
  isSelected: boolean;
  // Visual helpers
  pulseSpeed: number;
}

export const AgentStateVisual: Record<
  AgentState,
  { color: string; emissive: number; orbitSpeed: number; pulse: number }
> = {
  idle: { color: "#52525b", emissive: 0.1, orbitSpeed: 0, pulse: 0 },
  queued: { color: "#71717a", emissive: 0.2, orbitSpeed: 0.1, pulse: 0.5 },
  planning: { color: "#a78bfa", emissive: 0.4, orbitSpeed: 0.3, pulse: 1.5 },
  running: { color: "#8b5cf6", emissive: 0.8, orbitSpeed: 0.8, pulse: 0.8 },
  tool_calling: { color: "#22d3ee", emissive: 1.0, orbitSpeed: 1.0, pulse: 0.4 },
  waiting_approval: { color: "#fbbf24", emissive: 0.6, orbitSpeed: 0.1, pulse: 2.0 },
  waiting_dependency: { color: "#60a5fa", emissive: 0.3, orbitSpeed: 0.2, pulse: 1.0 },
  completed: { color: "#34d399", emissive: 0.3, orbitSpeed: 0, pulse: 0 },
  failed: { color: "#f87171", emissive: 1.2, orbitSpeed: 0, pulse: 0.2 },
  cancelled: { color: "#52525b", emissive: 0.1, orbitSpeed: 0, pulse: 0 },
};

export type MissionState = "idle" | "active" | "needs_attention" | "completed" | "failed";
