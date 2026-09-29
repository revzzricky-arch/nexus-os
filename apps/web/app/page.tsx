"use client";

import dynamic from "next/dynamic";
import { AppShell } from "@/components/layout/AppShell";
import { MissionHeader } from "@/components/mission/MissionHeader";
import { MissionComposer } from "@/components/mission/MissionComposer";
import { AgentCards } from "@/components/mission/AgentCards";
import { TaskProgress } from "@/components/mission/TaskProgress";
import { ActivityFeed } from "@/components/mission/ActivityFeed";
import { MissionSummary } from "@/components/mission/MissionSummary";
import { DetailPanel } from "@/components/mission/DetailPanel";
import { ApprovalModal } from "@/components/mission/ApprovalModal";
import { useRuntimeStore, useSelectedAgent, useSelectedTask, useSelectedApproval } from "@/lib/store/runtime";
import { useEffect } from "react";

// Dynamic import for 3D canvas - no SSR, performance
const MissionCanvas = dynamic(() => import("@/components/3d/Scene"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-zinc-900/50 rounded-xl border border-zinc-800">
      <div className="text-center space-y-3">
        <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mx-auto" />
        <p className="text-sm text-zinc-400">Initializing 3D Runtime...</p>
        <p className="text-[11px] text-zinc-600">Hybrid Orbital + Layered DAG</p>
      </div>
    </div>
  ),
});

export default function MissionControlPage() {
  const activeMission = useRuntimeStore((s) => s.activeMission);
  const agents = useRuntimeStore((s) => s.agents);
  const tasks = useRuntimeStore((s) => s.tasks);
  const events = useRuntimeStore((s) => s.events);
  const approvals = useRuntimeStore((s) => s.approvals);
  const selectedAgentId = useRuntimeStore((s) => s.selectedAgentId);
  const selectedTaskId = useRuntimeStore((s) => s.selectedTaskId);
  const selectedApprovalId = useRuntimeStore((s) => s.selectedApprovalId);
  const is3DEnabled = useRuntimeStore((s) => s.is3DEnabled);
  const showApprovalModal = useRuntimeStore((s) => s.showApprovalModal);
  const modalApprovalId = useRuntimeStore((s) => s.modalApprovalId);
  const setSelectedAgent = useRuntimeStore((s) => s.setSelectedAgent);
  const setSelectedTask = useRuntimeStore((s) => s.setSelectedTask);
  const setSelectedApproval = useRuntimeStore((s) => s.setSelectedApproval);
  const set3DEnabled = useRuntimeStore((s) => s.set3DEnabled);
  const approveApproval = useRuntimeStore((s) => s.approveApproval);
  const denyApproval = useRuntimeStore((s) => s.denyApproval);
  const openApprovalModal = useRuntimeStore((s) => s.openApprovalModal);
  const closeApprovalModal = useRuntimeStore((s) => s.closeApprovalModal);

  const selectedAgent = useSelectedAgent();
  const selectedTask = useSelectedTask();
  const selectedApproval = useSelectedApproval();
  const modalApproval = approvals.find((a) => a.id === modalApprovalId) || null;

  // Simulate live events for demo
  useEffect(() => {
    const interval = setInterval(() => {
      // Only simulate if mission running
      if (activeMission?.status === "running") {
        useRuntimeStore.getState().simulateEvent();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [activeMission?.status]);

  if (!activeMission) {
    return (
      <AppShell>
        <div className="p-8 text-center text-zinc-500">No active mission</div>
      </AppShell>
    );
  }

  const hasDetail = !!(selectedAgent || selectedTask || selectedApproval);

  return (
    <AppShell>
      <div className="flex flex-col min-h-[calc(100vh-49px)]">
        {/* Mission Header */}
        <MissionHeader mission={activeMission} />

        {/* Main grid: ~60% 3D runtime ~40% contextual - desktop, responsive 2D-first mobile */}
        <div className="flex-1 flex flex-col xl:flex-row min-h-0">
          {/* Left: 3D + composer */}
          <div className="flex-1 flex flex-col min-w-0 xl:w-[60%]">
            {/* 3D Canvas */}
            <div className="relative h-[480px] xl:h-[640px] border-b xl:border-b-0 xl:border-r border-zinc-800 bg-zinc-950/50">
              <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-3">
                <div className="flex items-center gap-2">
                  <h2 className="text-xs font-medium text-zinc-300">Mission Runtime</h2>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-300">
                    Hybrid Orbital + DAG
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 border border-zinc-700 text-zinc-500 font-mono">
                    {agents.length} agents • {tasks.length} tasks
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => set3DEnabled(!is3DEnabled)}
                    className="text-[11px] px-2.5 py-1 rounded-full bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
                  >
                    {is3DEnabled ? "2D Fallback" : "Enable 3D"}
                  </button>
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                </div>
              </div>

              <div className="absolute inset-0 pt-[48px]">
                {is3DEnabled ? (
                  <MissionCanvas
                    selectedAgent={selectedAgentId}
                    onSelectAgent={setSelectedAgent}
                    selectedTask={selectedTaskId}
                    onSelectTask={setSelectedTask}
                    selectedApproval={selectedApprovalId}
                    onSelectApproval={(id) => {
                      if (id) {
                        const approval = approvals.find((a) => a.id === id);
                        if (approval) openApprovalModal(approval.id);
                      } else {
                        setSelectedApproval(null);
                      }
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center p-6">
                    <div className="text-center space-y-3 max-w-md">
                      <p className="text-sm text-zinc-400">3D disabled — 2D fallback per architecture</p>
                      <p className="text-xs text-zinc-600">Mission runtime data available in side panels. Mobile 2D-first simplified fallback.</p>
                      <div className="grid grid-cols-2 gap-2 pt-2">
                        {agents.map((a) => (
                          <div key={a.id} className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-left">
                            <div className="text-xs text-zinc-200">{a.name}</div>
                            <div className="text-[11px] text-zinc-500">{a.state}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Mission Composer - AI command interface */}
            <MissionComposer />
          </div>

          {/* Right: contextual panels ~40% */}
          <div className="flex-1 xl:w-[40%] xl:max-w-[480px] flex flex-col xl:flex-row min-w-0">
            <div className="flex-1 p-4 space-y-6 overflow-y-auto max-h-[800px] xl:max-h-[calc(100vh-49px-88px)]">
              <AgentCards agents={agents} selectedId={selectedAgentId} onSelect={setSelectedAgent} />
              <TaskProgress tasks={tasks} selectedId={selectedTaskId} onSelect={setSelectedTask} />
              <ActivityFeed events={events} />
              <MissionSummary mission={activeMission} />
            </div>

            {/* Detail panel - 2D primary info surface, not exclusively 3D dependent */}
            {hasDetail && (
              <DetailPanel
                agent={selectedAgent}
                task={selectedTask}
                approval={selectedApproval}
                onClose={() => {
                  setSelectedAgent(null);
                  setSelectedTask(null);
                  setSelectedApproval(null);
                }}
                onApprove={approveApproval}
                onDeny={denyApproval}
              />
            )}
          </div>
        </div>

        {/* Approval Modal - click approval gate opens 2D approval UI */}
        <ApprovalModal
          approval={modalApproval}
          isOpen={showApprovalModal}
          onClose={closeApprovalModal}
          onApprove={approveApproval}
          onDeny={denyApproval}
        />
      </div>
    </AppShell>
  );
}
