"use client";

/**
 * Event Adapter - Phase 2B-5
 *
 * Responsibilities:
 * - Dispatch EventEnvelope into Zustand runtime store
 * - Map real events to existing visual state:
 *   mission_status -> core
 *   agent_state -> AgentNode
 *   task_status -> TaskNode
 *   handoff -> edge activity
 *   tool_call -> tool activity
 *   approval -> gate
 *   error -> error state
 *   cost -> metrics
 * - Restrained visual language, no redesign
 */

import { useRuntimeStore } from "@/lib/store/runtime";
import type { EventEnvelope } from "./types";

// Mock types for mapping
type AgentState = "IDLE" | "PLANNING" | "RUNNING" | "WAITING" | "WAITING_FOR_APPROVAL" | "COMPLETED" | "FAILED" | "PAUSED";
type TaskState = "PENDING" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "BLOCKED";
type MissionStatus = "draft" | "running" | "awaiting_approval" | "completed" | "failed" | "paused";

interface MissionStatusPayload {
  from: string;
  to: string;
  mission_id: string;
}

interface TaskStatusPayload {
  from: string;
  to: string;
  task_id: string;
  title: string;
}

interface AgentStatePayload {
  from: string;
  to: string;
  reason?: string;
  agent_type: string;
}

interface ToolCallPayload {
  tool_id: string;
  tool_call_id: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: string;
  latency_ms?: number;
}

interface ApprovalPayload {
  approval_id: string;
  type: string;
  tool_id?: string;
  args?: Record<string, unknown>;
  reasoning?: string;
  risk_level?: string;
}

interface HandoffPayload {
  from_agent: string;
  to_agent: string;
  task_id: string;
  summary: string;
}

interface CostPayload {
  cost_cents: number;
  token_usage: number;
  mission_id: string;
}

interface ErrorPayload {
  message: string;
  code?: string;
  task_id?: string;
  agent_id?: string;
}

export class RuntimeEventAdapter {
  // Dispatch EventEnvelope into Zustand store
  dispatch(envelope: EventEnvelope) {
    const store = useRuntimeStore.getState();

    // Always append to events list for ActivityFeed (keep last 100)
    // Convert to MockEvent shape for backward compat
    const mockEvent = {
      id: envelope.id,
      timestamp: envelope.timestamp,
      mission_id: envelope.mission_id,
      type: envelope.type,
      source: envelope.source,
      payload: envelope.payload,
      task_id: envelope.task_id || undefined,
      agent_id: envelope.agent_id || undefined,
    };

    // Update events - preserve existing, prepend new
    useRuntimeStore.setState((state) => ({
      events: [mockEvent as any, ...state.events.slice(0, 99)],
    }));

    // Map by type
    switch (envelope.type) {
      case "mission_status_changed":
      case "mission_created":
        this.handleMissionStatus(envelope as EventEnvelope<MissionStatusPayload>);
        break;
      case "task_status_changed":
        this.handleTaskStatus(envelope as EventEnvelope<TaskStatusPayload>);
        break;
      case "agent_state_changed":
        this.handleAgentState(envelope as EventEnvelope<AgentStatePayload>);
        break;
      case "tool_call_started":
      case "tool_call_completed":
      case "tool_call_failed":
        this.handleToolCall(envelope as EventEnvelope<ToolCallPayload>);
        break;
      case "approval_requested":
      case "approval_decided":
        this.handleApproval(envelope as EventEnvelope<ApprovalPayload>);
        break;
      case "handoff":
        this.handleHandoff(envelope as EventEnvelope<HandoffPayload>);
        break;
      case "cost_updated":
        this.handleCost(envelope as EventEnvelope<CostPayload>);
        break;
      case "error":
        this.handleError(envelope as EventEnvelope<ErrorPayload>);
        break;
      default:
        // Other events already added to feed
        break;
    }
  }

  private handleMissionStatus(envelope: EventEnvelope<MissionStatusPayload>) {
    const payload = envelope.payload;
    if (!payload) return;

    const toStatus = payload.to as MissionStatus;
    // Map to existing store: activeMission status -> core
    useRuntimeStore.setState((state) => {
      if (!state.activeMission) return state;
      // Only update if mission_id matches active
      if (state.activeMission.id !== envelope.mission_id) return state;

      // Map status vocabulary: draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived
      // To mock: draft, running, awaiting_approval, completed, failed, paused
      let mapped: MissionStatus = state.activeMission.status;
      if (["running", "decomposing", "planned"].includes(toStatus)) mapped = "running";
      else if (["awaiting_approval"].includes(toStatus)) mapped = "awaiting_approval";
      else if (["completed", "archived"].includes(toStatus)) mapped = "completed";
      else if (["failed", "cancelled"].includes(toStatus)) mapped = "failed";
      else if (["paused", "draft"].includes(toStatus)) mapped = toStatus as MissionStatus;

      return {
        activeMission: {
          ...state.activeMission,
          status: mapped,
          phase: toStatus,
        },
        missions: state.missions.map((m) =>
          m.id === envelope.mission_id ? { ...m, status: mapped, phase: toStatus } : m
        ),
      };
    });
  }

  private handleTaskStatus(envelope: EventEnvelope<TaskStatusPayload>) {
    const payload = envelope.payload;
    if (!payload) return;

    const taskId = payload.task_id || (envelope.task_id as string);
    if (!taskId) return;

    const toStatus = payload.to?.toUpperCase() as TaskState;
    // Map to TaskNode: task_status -> TaskNode progress
    useRuntimeStore.setState((state) => ({
      tasks: state.tasks.map((t) => {
        if (t.id !== taskId && t.id !== envelope.task_id) return t;
        let progress = t.progress;
        if (toStatus === "COMPLETED") progress = 100;
        else if (toStatus === "RUNNING") progress = Math.max(progress, 30);
        else if (toStatus === "QUEUED") progress = Math.max(progress, 5);

        return {
          ...t,
          status: (toStatus as any) || t.status,
          progress,
        };
      }),
    }));
  }

  private handleAgentState(envelope: EventEnvelope<AgentStatePayload>) {
    const payload = envelope.payload;
    if (!payload) return;

    const agentId = envelope.agent_id as string;
    if (!agentId) return;

    const toState = payload.to?.toUpperCase() as AgentState;

    // Map agent_state -> AgentNode
    useRuntimeStore.setState((state) => ({
      agents: state.agents.map((a) => {
        if (a.id !== agentId) return a;
        return {
          ...a,
          state: (toState as any) || a.state,
          recent_activity: payload.reason || `State: ${payload.from} -> ${payload.to}`,
        };
      }),
    }));
  }

  private handleToolCall(envelope: EventEnvelope<ToolCallPayload>) {
    const payload = envelope.payload;
    if (!payload) return;

    // Map tool_call -> tool activity (update tool call count, recent activity)
    useRuntimeStore.setState((state) => ({
      tools: state.tools.map((tool) => {
        if (tool.id !== payload.tool_id) return tool;
        return {
          ...tool,
          call_count: tool.call_count + 1,
          avg_latency_ms: payload.latency_ms || tool.avg_latency_ms,
          state: payload.status === "failed" ? "error" : "active",
        } as any;
      }),
      agents: state.agents.map((a) => {
        if (envelope.agent_id && a.id === envelope.agent_id) {
          return {
            ...a,
            recent_activity: `Tool ${payload.tool_id} ${payload.status}`,
          };
        }
        return a;
      }),
    }));
  }

  private handleApproval(envelope: EventEnvelope<ApprovalPayload>) {
    const payload = envelope.payload;
    if (!payload) return;

    if (envelope.type === "approval_requested") {
      // Add approval gate
      useRuntimeStore.setState((state) => ({
        approvals: [
          {
            id: payload.approval_id,
            mission_id: envelope.mission_id,
            task_id: (envelope.task_id as string) || "",
            agent_id: (envelope.agent_id as string) || "",
            tool_id: payload.tool_id || "",
            type: payload.type as any,
            status: "PENDING" as any,
            risk_level: (payload.risk_level as any) || "medium",
            requested_action: payload.tool_id || payload.type,
            args: payload.args || {},
            reasoning: payload.reasoning || "",
            created_at: envelope.timestamp,
            agent_name: "Agent",
          } as any,
          ...state.approvals.slice(0, 19),
        ],
      }));
    } else if (envelope.type === "approval_decided") {
      // Update approval status - do NOT allow frontend-only override, backend truth is authoritative
      // UI shape preserved
      useRuntimeStore.setState((state) => ({
        approvals: state.approvals.map((ap) =>
          ap.id === payload.approval_id
            ? { ...ap, status: (payload as any).decision?.toUpperCase() || ap.status }
            : ap
        ),
      }));
    }
  }

  private handleHandoff(envelope: EventEnvelope<HandoffPayload>) {
    const payload = envelope.payload;
    if (!payload) return;

    // Handoff -> edge activity (update agent recent_activity)
    useRuntimeStore.setState((state) => ({
      agents: state.agents.map((a) => {
        if (a.id === payload.from_agent) {
          return { ...a, recent_activity: `Handoff to ${payload.to_agent}: ${payload.summary.slice(0, 60)}` };
        }
        if (a.id === payload.to_agent) {
          return { ...a, recent_activity: `Received from ${payload.from_agent}: ${payload.summary.slice(0, 60)}` };
        }
        return a;
      }),
    }));
  }

  private handleCost(envelope: EventEnvelope<CostPayload>) {
    const payload = envelope.payload;
    if (!payload) return;

    // Cost -> metrics
    useRuntimeStore.setState((state) => {
      if (!state.activeMission) return state;
      if (state.activeMission.id !== envelope.mission_id) return state;
      return {
        activeMission: {
          ...state.activeMission,
          cost_cents: payload.cost_cents,
          token_usage: payload.token_usage,
        },
      };
    });
  }

  private handleError(envelope: EventEnvelope<ErrorPayload>) {
    const payload = envelope.payload;
    if (!payload) return;

    // Error -> error state
    useRuntimeStore.setState((state) => ({
      agents: state.agents.map((a) => {
        if (envelope.agent_id && a.id === envelope.agent_id) {
          return { ...a, state: "FAILED" as any, recent_activity: `Error: ${payload.message.slice(0, 80)}` };
        }
        return a;
      }),
      tasks: state.tasks.map((t) => {
        if (envelope.task_id && t.id === envelope.task_id) {
          return { ...t, status: "FAILED" as any };
        }
        return t;
      }),
    }));
  }
}

// Singleton
export const runtimeEventAdapter = new RuntimeEventAdapter();
