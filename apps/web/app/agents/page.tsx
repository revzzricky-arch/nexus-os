"use client";

import { AppShell } from "@/components/layout/AppShell";
import { useRuntimeStore } from "@/lib/store/runtime";
import { Badge } from "@/components/ui/badge";
import { Bot, Cpu, Clock, Zap, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export default function AgentsPage() {
  const agents = useRuntimeStore((s) => s.agents);
  const selectedId = useRuntimeStore((s) => s.selectedAgentId);
  const setSelected = useRuntimeStore((s) => s.setSelectedAgent);

  const getStateVariant = (state: string) => {
    switch (state) {
      case "RUNNING":
        return "default";
      case "COMPLETED":
        return "success";
      case "WAITING_FOR_APPROVAL":
        return "warning";
      case "FAILED":
        return "error";
      case "PAUSED":
        return "secondary";
      default:
        return "muted";
    }
  };

  return (
    <AppShell>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-zinc-100 tracking-tight">Agents</h1>
            <p className="text-sm text-zinc-500 mt-1">Supervisor, Researcher, Coder, Analyst • Mock runtime</p>
          </div>
          <Badge variant="secondary" className="font-mono">
            {agents.length} agents
          </Badge>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {agents.map((agent) => {
            const isSelected = selectedId === agent.id;
            return (
              <button
                key={agent.id}
                onClick={() => setSelected(isSelected ? null : agent.id)}
                className={cn(
                  "text-left p-4 rounded-xl border transition-all",
                  isSelected ? "bg-violet-500/10 border-violet-500/30" : "bg-zinc-900 border-zinc-800 hover:border-zinc-700"
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "w-10 h-10 rounded-xl flex items-center justify-center",
                        agent.type === "supervisor"
                          ? "bg-violet-500/15 border border-violet-500/20"
                          : agent.type === "researcher"
                          ? "bg-cyan-500/10 border border-cyan-500/20"
                          : agent.type === "coder"
                          ? "bg-amber-500/10 border border-amber-500/20"
                          : "bg-emerald-500/10 border border-emerald-500/20"
                      )}
                    >
                      <Bot className="w-5 h-5 text-zinc-300" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-zinc-100">{agent.name}</div>
                      <div className="text-xs text-zinc-500">{agent.role}</div>
                    </div>
                  </div>
                  <Badge variant={getStateVariant(agent.state) as any} className="text-[10px]">
                    {agent.state}
                  </Badge>
                </div>

                <div className="mt-3 space-y-2">
                  <div className="text-xs text-zinc-300">
                    <span className="text-zinc-500">Task:</span> {agent.current_task_title || "Idle"}
                  </div>
                  <div className="text-xs text-zinc-500 line-clamp-2 leading-relaxed">{agent.recent_activity}</div>

                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {agent.capabilities.map((cap) => (
                      <Badge key={cap} variant="muted" className="text-[10px] font-mono">
                        {cap}
                      </Badge>
                    ))}
                  </div>

                  <div className="flex items-center justify-between pt-2 text-[11px] text-zinc-600 font-mono">
                    <span className="flex items-center gap-1">
                      <Cpu className="w-3 h-3" />
                      {agent.token_usage} tokens • ${(agent.cost_cents / 100).toFixed(2)}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-500">{agent.model}</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="grid gap-3 md:grid-cols-2 text-[11px] text-zinc-600">
          <div className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
            <div className="text-zinc-400 font-medium mb-1">Agent Types • D5 Hybrid Orbital</div>
            Supervisor = planner & orchestrator, Researcher = web + RAG, Coder = sandbox files + shell, Analyst = synthesis. Orbital radius 2.8+ idx*0.3, distinct geometry.
          </div>
          <div className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
            <div className="text-zinc-400 font-medium mb-1">States • Restrained Visuals</div>
            IDLE static, PLANNING slow pulse, RUNNING active pulse/orbit, WAITING subdued, WAITING_FOR_APPROVAL amber indicator, COMPLETED settled, FAILED error, PAUSED dimmed.
          </div>
        </div>
      </div>
    </AppShell>
  );
}
