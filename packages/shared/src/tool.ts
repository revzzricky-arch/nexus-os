import { UUID, ISODateTime, RiskLevel, PermissionLevel } from "./common";

export type ToolSource = "builtin" | "mcp";
export type MCPTransport = "stdio" | "streamable_http" | "sse_legacy"; // per review: stdio local, Streamable HTTP remote, SSE legacy only

export interface ToolRegistryEntry {
  id: string; // e.g., write_file
  name: string;
  description: string;
  source: ToolSource;
  mcp_server_id?: UUID;
  input_schema: Record<string, unknown>; // JSON Schema
  output_schema?: Record<string, unknown>;
  capability_tags: string[];
  risk_level: RiskLevel;
  default_permission: PermissionLevel;
  sandbox_config: {
    service: "SandboxService";
    isolation: "container" | "scoped_fs";
    allowed_paths?: string[]; // e.g., ["mission_workspace"]
    note?: string;
  };
}

export interface MCPServerConfig {
  id: UUID;
  name: string;
  transport: MCPTransport;
  command?: string; // for stdio
  url?: string; // for streamable_http / sse_legacy
  env?: Record<string, string>; // secret refs, not raw secrets
  enabled: boolean;
  status: "disconnected" | "connected" | "error";
  last_seen?: ISODateTime;
}

export interface ToolCall {
  id: UUID;
  agent_run_id: UUID;
  task_id: UUID;
  tool_id: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: "pending" | "running" | "success" | "failed" | "denied";
  permission_decision?: {
    permission: PermissionLevel;
    reason: string;
    requires_approval: boolean;
  };
  approval_id?: UUID;
  latency_ms?: number;
  created_at: ISODateTime;
}

// 3D tool activity visualization - runtime only
export interface ToolActivity3D {
  id: UUID;
  tool_id: string;
  from_agent_position: [number, number, number];
  to_position: [number, number, number]; // tool orb or core
  status: ToolCall["status"];
  risk_level: RiskLevel;
  color: string;
  duration_ms: number;
}

export const RiskLevelColor: Record<RiskLevel, string> = {
  low: "#22d3ee",
  medium: "#fbbf24",
  high: "#f87171",
  critical: "#ef4444",
};
