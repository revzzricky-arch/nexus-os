import { UUID, ISODateTime, Timestamps, CostTracking } from "./common";
import { AgentType } from "./agent";

export type TaskStatus =
  | "pending"
  | "queued"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled"
  | "skipped";

export interface Task extends Timestamps, CostTracking {
  id: UUID;
  mission_id: UUID;
  title: string;
  description?: string;
  agent_type: AgentType;
  status: TaskStatus;
  dependencies: UUID[];
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  error?: string;
  retry_count: number;
  max_retries: number;
}

export interface TaskCreate {
  title: string;
  description?: string;
  agent_type: AgentType;
  dependencies?: UUID[];
  input?: Record<string, unknown>;
}

// 3D state for task nodes - layered DAG
export interface Task3DState {
  id: UUID;
  status: TaskStatus;
  position: [number, number, number]; // layered DAG layout
  layer: number; // dependency depth
  indexInLayer: number;
  dependencyEdges: UUID[];
  progress: number; // 0-1
  isSelected: boolean;
  color: string;
}

export const TaskStatusColor: Record<TaskStatus, string> = {
  pending: "#27272a",
  queued: "#52525b",
  running: "#8b5cf6",
  awaiting_approval: "#fbbf24",
  completed: "#10b981",
  failed: "#ef4444",
  cancelled: "#52525b",
  skipped: "#3f3f46",
};
