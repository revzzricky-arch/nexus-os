"use client";

import { create } from "zustand";

// Scaffold Zustand store for mission 3D state
// Runtime focus only: agents, tasks, workflows, tool activity, approval gates

interface MissionStore {
  selectedAgent: string | null;
  selectedTask: string | null;
  is3DEnabled: boolean;
  setSelectedAgent: (id: string | null) => void;
  setSelectedTask: (id: string | null) => void;
  set3DEnabled: (enabled: boolean) => void;
  // Future: agents, tasks, approvals, tool activities from WS
}

export const useMissionStore = create<MissionStore>((set) => ({
  selectedAgent: null,
  selectedTask: null,
  is3DEnabled: true,
  setSelectedAgent: (id) => set({ selectedAgent: id }),
  setSelectedTask: (id) => set({ selectedTask: id }),
  set3DEnabled: (enabled) => set({ is3DEnabled: enabled }),
}));
