import { UUID, ISODateTime, Timestamps } from "./common";

export type ApprovalType = "tool" | "task" | "mission";
export type ApprovalStatus = "pending" | "approved" | "denied" | "expired";

export interface Approval extends Timestamps {
  id: UUID;
  mission_id: UUID;
  task_id?: UUID;
  agent_run_id?: UUID;
  tool_call_id?: UUID;
  type: ApprovalType;
  status: ApprovalStatus;
  requested_by: string; // agent id or system
  requested_payload: {
    tool_id?: string;
    args?: Record<string, unknown>;
    reasoning?: string;
    risk_level?: string;
    diff?: string; // for file writes
  };
  reviewed_by?: UUID;
  review_comment?: string;
  reviewed_at?: ISODateTime;
  expires_at?: ISODateTime;
}

export interface ApprovalDecision {
  decision: "approved" | "denied";
  comment?: string;
  edited_args?: Record<string, unknown>; // user can edit args and approve
}

// 3D approval gate visualization - runtime only
export interface ApprovalGate3DState {
  id: UUID;
  approval_id: UUID;
  position: [number, number, number]; // on workflow edge
  edge_from: UUID; // task id
  edge_to: UUID; // task id
  status: ApprovalStatus;
  type: ApprovalType;
  isSelected: boolean;
  color: string;
  rotation: number; // for animation
  pulseScale: number;
}

export const ApprovalStatusColor: Record<ApprovalStatus, string> = {
  pending: "#fbbf24",
  approved: "#34d399",
  denied: "#f87171",
  expired: "#52525b",
};
