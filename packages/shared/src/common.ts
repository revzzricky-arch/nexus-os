// Common primitives

export type UUID = string; // UUID v4 string
export type ISODateTime = string; // ISO 8601

export interface Timestamps {
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface PaginationParams {
  limit?: number;
  offset?: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  limit: number;
  offset: number;
}

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type PermissionLevel = "forbidden" | "approval_required" | "auto" | "read_only_auto";

export interface CostTracking {
  token_usage: number;
  cost_cents: number;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
