"use client";

// Runtime mode - default safe mock, realtime opt-in
export type RuntimeMode = "mock" | "realtime";

// Realtime EventEnvelope - mirrors backend shared contract
// Authoritative: packages/shared/src/events.ts
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

export interface EventEnvelope<T = unknown> {
  id: string;
  type: EventType;
  source: string;
  mission_id: string;
  task_id?: string | null;
  agent_id?: string | null;
  timestamp: string;
  version: number;
  payload: T;
  metadata?: Record<string, unknown>;
}

// WS Protocol - separate from EventEnvelope
export type WSClientMessage =
  | { type: "auth"; token: string }
  | { type: "subscribe"; mission_id: string; last_event_id?: string | null }
  | { type: "unsubscribe"; mission_id: string }
  | { type: "ping" };

export type WSServerMessage =
  | { type: "welcome"; message: string; version: number }
  | { type: "auth_ok" }
  | { type: "auth_error"; code: string; message: string }
  | { type: "subscribed"; mission_id: string; last_event_id?: string | null; replay_count: number }
  | { type: "unsubscribed"; mission_id: string }
  | { type: "pong" }
  | { type: "error"; code: string; message: string }
  | EventEnvelope; // event stream uses envelope directly

// Connection lifecycle
export type WSConnectionState =
  | "CONNECTING"
  | "AUTHENTICATING"
  | "AUTHENTICATED"
  | "SUBSCRIBED"
  | "CLOSED";

// Limits documented
export const WS_LIMITS = {
  MAX_MESSAGE_SIZE: 32 * 1024,
  AUTH_TIMEOUT: 10_000,
  MAX_SUBS_PER_SOCKET: 10,
  MAX_CONNECTIONS: 100,
  MAX_REPLAY_BATCH: 100,
  INITIAL_BACKOFF_MS: 1000,
  MAX_BACKOFF_MS: 30_000,
  BACKOFF_MULTIPLIER: 2,
  HEARTBEAT_INTERVAL_MS: 30_000,
} as const;

// Runtime provider interface - same store shape for mock and realtime
export interface RuntimeProviderInterface {
  mode: RuntimeMode;
  connect: (missionId: string) => Promise<void>;
  disconnect: () => void;
  isConnected: boolean;
  lastEventId: string | null;
}
