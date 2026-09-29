import { UUID, ISODateTime } from "./common";

// Realtime Event Contract - Scaffold Phase
// Defines envelope only, no Redis/WS implementation yet
// Per review: avoid credentials in URLs for WS auth

export type EventType =
  | "agent_state_changed"
  | "task_status_changed"
  | "tool_call_started"
  | "tool_call_completed"
  | "tool_call_failed"
  | "message_created"
  | "approval_requested"
  | "approval_decided"
  | "mission_status_changed"
  | "mission_created"
  | "handoff"
  | "memory_created"
  | "memory_accessed"
  | "rag_queried"
  | "error"
  | "cost_updated";

export type EventSource = "agent_runner" | "supervisor" | "tool_registry" | "approval_service" | "memory_service" | "system" | "user";

export interface EventEnvelope<T = unknown> {
  id: UUID;
  type: EventType;
  source: EventSource;
  mission_id: UUID;
  task_id?: UUID;
  agent_id?: UUID;
  timestamp: ISODateTime;
  version: number; // schema version, e.g., 1
  payload: T;
  metadata?: {
    trace_id?: string;
    span_id?: string;
    user_id?: UUID;
    // No secrets in metadata
  };
}

// Specific payload types (scaffold)

export interface AgentStateChangedPayload {
  from: string;
  to: string;
  reason?: string;
  agent_type: string;
}

export interface TaskStatusChangedPayload {
  from: string;
  to: string;
  task_id: UUID;
  title: string;
}

export interface ToolCallPayload {
  tool_id: string;
  tool_call_id: UUID;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: "pending" | "running" | "success" | "failed" | "denied";
  latency_ms?: number;
}

export interface ApprovalRequestedPayload {
  approval_id: UUID;
  type: "tool" | "task" | "mission";
  tool_id?: string;
  args?: Record<string, unknown>;
  reasoning?: string;
  risk_level?: string;
}

export interface MissionStatusChangedPayload {
  from: string;
  to: string;
  mission_id: UUID;
}

export interface HandoffPayload {
  from_agent: UUID;
  to_agent: UUID;
  task_id: UUID;
  summary: string;
  artifacts?: UUID[];
}

export interface ErrorPayload {
  message: string;
  code?: string;
  stack?: string; // only in dev, not prod
  task_id?: UUID;
  agent_id?: UUID;
}

// WS Auth - Scaffold Approach (avoid ?token=SECRET in URL)
// Per security requirement: Do NOT use ?token=SECRET in URL
// Chosen scaffold approach: Initial auth message after WS connection
export interface WSAuthMessage {
  type: "auth";
  // For scaffold: use secure header or initial message, not URL
  // In production: httpOnly cookie + initial auth message with Bearer token
  // For dev: client sends {type: "auth", token: "Bearer <dev-token>"} as first message
  // Server validates and then allows subscriptions
  token: string; // Bearer token value, sent as first WS message, not in URL
}

export interface WSSubscribeMessage {
  type: "subscribe";
  channels: string[]; // e.g., ["mission:uuid", "approvals"]
  last_event_id?: UUID; // for replay from Redis Stream
}

export interface WSUnsubscribeMessage {
  type: "unsubscribe";
  channels: string[];
}

export type WSClientMessage = WSAuthMessage | WSSubscribeMessage | WSUnsubscribeMessage;

export interface WSServerMessage {
  type: "event" | "subscribed" | "unsubscribed" | "error" | "pong";
  channel?: string;
  event?: EventEnvelope;
  message?: string;
}

// For 3D frontend/backend data flow - runtime state only
export interface Runtime3DState {
  mission_id: UUID;
  mission_core: {
    status: string;
    cost: { tokens: number; cents: number };
    hasMemoryActivity: boolean; // abstract indicator, not raw DB
  };
  agents: Array<{
    id: UUID;
    type: string;
    status: string;
    orbitIndex: number;
    toolCallCount: number;
    hasApproval: boolean;
  }>;
  tasks: Array<{
    id: UUID;
    status: string;
    layer: number;
    dependencies: UUID[];
  }>;
  approvals: Array<{
    id: UUID;
    status: string;
    edge_from: UUID;
    edge_to: UUID;
  }>;
  tool_activities: Array<{
    id: UUID;
    from_agent: UUID;
    tool_id: string;
    status: string;
  }>;
}
