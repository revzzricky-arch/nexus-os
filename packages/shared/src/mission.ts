import { UUID, ISODateTime, Timestamps, CostTracking } from "./common";

export type MissionStatus =
  | "draft"
  | "decomposing"
  | "planned"
  | "running"
  | "awaiting_approval"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled"
  | "archived";

export type MissionTemplate = "research" | "code" | "analysis" | "general";

export interface MissionDAG {
  // adjacency list: task_id -> dependent task_ids
  nodes: UUID[];
  edges: Array<{ from: UUID; to: UUID }>;
  // For 3D layered layout: layer = max dependency depth
  layers?: Record<UUID, number>;
}

export interface ApprovalPolicy {
  tools: Record<string, "always" | "never" | "on_risk">;
  tasks: string[]; // task titles requiring approval
  mission_plan: boolean;
  // Balanced policy per D6: shell always approval
  shell_always_approval: boolean;
}

export interface Mission extends Timestamps, CostTracking {
  id: UUID;
  user_id: UUID;
  title: string;
  goal: string;
  status: MissionStatus;
  template: MissionTemplate;
  dag: MissionDAG | null;
  approval_policy: ApprovalPolicy;
  budget_tokens?: number;
  budget_cost_cents?: number;
}

export interface MissionCreate {
  title: string;
  goal: string;
  template: MissionTemplate;
  approval_policy?: Partial<ApprovalPolicy>;
  budget_tokens?: number;
}

export interface MissionUpdate {
  status?: MissionStatus;
  title?: string;
}

// 3D state mapping for mission core
export interface MissionCore3DState {
  id: UUID;
  status: MissionStatus;
  cost: CostTracking;
  // Visual properties
  color: string;
  emissiveIntensity: number;
  pulseSpeed: number;
  hasActiveMemoryActivity: boolean; // abstract indicator, not raw DB
}

export const MissionStatusColor: Record<MissionStatus, string> = {
  draft: "#52525b",
  decomposing: "#a78bfa",
  planned: "#71717a",
  running: "#8b5cf6",
  awaiting_approval: "#fbbf24",
  paused: "#60a5fa",
  completed: "#34d399",
  failed: "#f87171",
  cancelled: "#52525b",
  archived: "#27272a",
};
