"use client";

import { create } from "zustand";
import {
  mockMissions,
  mockAgents,
  mockTasks,
  mockTools,
  mockApprovals,
  mockEvents,
  type MockMission,
  type MockAgent,
  type MockTask,
  type MockTool,
  type MockApproval,
  type MockEvent,
  type AgentState,
  type TaskState,
  type MissionStatus,
  type ApprovalStatus,
} from "@/lib/mock/data";

interface RuntimeState {
  // Data
  missions: MockMission[];
  agents: MockAgent[];
  tasks: MockTask[];
  tools: MockTool[];
  approvals: MockApproval[];
  events: MockEvent[];
  activeMission: MockMission | null;

  // Selection
  selectedAgentId: string | null;
  selectedTaskId: string | null;
  selectedApprovalId: string | null;
  is3DEnabled: boolean;
  isComposing: boolean;
  composerValue: string;
  composerType: MockMission["type"];

  // UI
  showApprovalModal: boolean;
  modalApprovalId: string | null;

  // Actions
  setSelectedAgent: (id: string | null) => void;
  setSelectedTask: (id: string | null) => void;
  setSelectedApproval: (id: string | null) => void;
  set3DEnabled: (enabled: boolean) => void;
  setComposing: (composing: boolean) => void;
  setComposerValue: (value: string) => void;
  setComposerType: (type: MockMission["type"]) => void;
  setActiveMission: (mission: MockMission | null) => void;
  openApprovalModal: (id: string) => void;
  closeApprovalModal: () => void;
  approveApproval: (id: string) => void;
  denyApproval: (id: string) => void;
  runMission: (goal: string, type: MockMission["type"]) => void;
  simulateEvent: () => void;
  // Future: replace mock with real WS
  // In future, this store will be updated via WS events: EventEnvelope -> update agents/tasks/etc.
}

// Module-scoped interval handle for lifecycle-safe simulation - prevents overlapping intervals
let missionProgressInterval: ReturnType<typeof setInterval> | null = null;

function clearMissionInterval() {
  if (missionProgressInterval) {
    clearInterval(missionProgressInterval);
    missionProgressInterval = null;
  }
}

export const useRuntimeStore = create<RuntimeState>((set, get) => ({
  missions: mockMissions,
  agents: mockAgents,
  tasks: mockTasks,
  tools: mockTools,
  approvals: mockApprovals,
  events: mockEvents,
  activeMission: mockMissions[0],

  selectedAgentId: null,
  selectedTaskId: null,
  selectedApprovalId: null,
  is3DEnabled: true,
  isComposing: false,
  composerValue: "",
  composerType: "General",

  showApprovalModal: false,
  modalApprovalId: null,

  setSelectedAgent: (id) => set({ selectedAgentId: id, selectedTaskId: null, selectedApprovalId: null }),
  setSelectedTask: (id) => set({ selectedTaskId: id, selectedAgentId: null, selectedApprovalId: null }),
  setSelectedApproval: (id) => set({ selectedApprovalId: id }),
  set3DEnabled: (enabled) => set({ is3DEnabled: enabled }),
  setComposing: (composing) => set({ isComposing: composing }),
  setComposerValue: (value) => set({ composerValue: value }),
  setComposerType: (type) => set({ composerType: type }),
  setActiveMission: (mission) => set({ activeMission: mission }),

  openApprovalModal: (id) => set({ showApprovalModal: true, modalApprovalId: id, selectedApprovalId: id }),
  closeApprovalModal: () => set({ showApprovalModal: false, modalApprovalId: null }),

  approveApproval: (id) =>
    set((state) => ({
      approvals: state.approvals.map((a) => (a.id === id ? { ...a, status: "APPROVED" as ApprovalStatus } : a)),
      showApprovalModal: false,
      modalApprovalId: null,
      // Simulate agent state change after approval
      agents: state.agents.map((ag) =>
        ag.id === state.approvals.find((ap) => ap.id === id)?.agent_id
          ? { ...ag, state: "RUNNING" as AgentState, recent_activity: "Approval granted, continuing task" }
          : ag
      ),
    })),

  denyApproval: (id) =>
    set((state) => ({
      approvals: state.approvals.map((a) => (a.id === id ? { ...a, status: "DENIED" as ApprovalStatus } : a)),
      showApprovalModal: false,
      modalApprovalId: null,
    })),

  runMission: (goal, type) => {
    // Lifecycle-safe: prevent multiple overlapping progress intervals
    clearMissionInterval();

    const newMission: MockMission = {
      id: `mission-${Date.now()}`,
      title: goal.slice(0, 60) || "New Mission",
      goal,
      type,
      status: "running" as MissionStatus,
      progress: 5,
      elapsed_seconds: 0,
      phase: "Decomposing",
      agent_count: 4,
      task_count: 5,
      completed_tasks: 0,
      created_at: new Date().toISOString(),
      cost_cents: 0,
      token_usage: 0,
    };

    set((state) => ({
      missions: [newMission, ...state.missions],
      activeMission: newMission,
      isComposing: false,
      composerValue: "",
      // Reset tasks to simulate new mission
      tasks: mockTasks.map((t) => ({ ...t, status: "PENDING" as TaskState, progress: 0 })),
      agents: mockAgents.map((a) => ({ ...a, state: "PLANNING" as AgentState })),
    }));

    // Simulate progress over time (mock runtime) - lifecycle-safe with cleanup
    let progress = 5;
    missionProgressInterval = setInterval(() => {
      progress += Math.random() * 5;
      if (progress >= 100) {
        progress = 100;
        clearMissionInterval();
        set((state) => ({
          activeMission: state.activeMission ? { ...state.activeMission, status: "completed", progress: 100, phase: "Completed" } : null,
          tasks: state.tasks.map((t) => ({ ...t, status: "COMPLETED" as TaskState, progress: 100 })),
          agents: state.agents.map((a) => ({ ...a, state: "COMPLETED" as AgentState })),
        }));
      } else {
        set((state) => ({
          activeMission: state.activeMission ? { ...state.activeMission, progress, elapsed_seconds: state.activeMission.elapsed_seconds + 2 } : null,
        }));
      }
    }, 2000);
  },

  simulateEvent: () => {
    // Simulate random agent state change for demo
    const states: AgentState[] = ["IDLE", "PLANNING", "RUNNING", "WAITING", "WAITING_FOR_APPROVAL", "COMPLETED"];
    set((state) => ({
      agents: state.agents.map((a) =>
        Math.random() > 0.7 ? { ...a, state: states[Math.floor(Math.random() * states.length)] } : a
      ),
      events: [
        {
          id: `evt-${Date.now()}`,
          timestamp: new Date().toISOString(),
          mission_id: state.activeMission?.id || "mission-1",
          type: "agent_state_changed",
          source: "agent_runner",
          payload: { simulated: true },
        },
        ...state.events.slice(0, 20),
      ],
    }));
  },
}));

// Selector helpers for 3D - runtime focus only
export const useSelectedAgent = () => {
  const selectedId = useRuntimeStore((s) => s.selectedAgentId);
  const agents = useRuntimeStore((s) => s.agents);
  return agents.find((a) => a.id === selectedId) || null;
};

export const useSelectedTask = () => {
  const selectedId = useRuntimeStore((s) => s.selectedTaskId);
  const tasks = useRuntimeStore((s) => s.tasks);
  return tasks.find((t) => t.id === selectedId) || null;
};

export const useSelectedApproval = () => {
  const selectedId = useRuntimeStore((s) => s.selectedApprovalId);
  const approvals = useRuntimeStore((s) => s.approvals);
  return approvals.find((a) => a.id === selectedId) || null;
};
