"use client";

import { AppShell } from "@/components/layout/AppShell";
import { useRuntimeStore } from "@/lib/store/runtime";
import { Badge } from "@/components/ui/badge";
import { Activity, Clock, Cpu, DollarSign, Bot, Wrench, AlertTriangle } from "lucide-react";

export default function ObservabilityPage() {
  const missions = useRuntimeStore((s) => s.missions);
  const agents = useRuntimeStore((s) => s.agents);
  const tools = useRuntimeStore((s) => s.tools);
  const events = useRuntimeStore((s) => s.events);

  const totalTokens = missions.reduce((acc, m) => acc + m.token_usage, 0);
  const totalCost = missions.reduce((acc, m) => acc + m.cost_cents, 0);
  const totalToolCalls = tools.reduce((acc, t) => acc + t.call_count, 0);

  return (
    <AppShell>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-zinc-100 tracking-tight">Observability</h1>
            <p className="text-sm text-zinc-500 mt-1">Metrics • Agent activity • Tool calls • Latency • Errors • Token/cost mock</p>
          </div>
          <Badge variant="secondary" className="font-mono">
            Mock • Future real metrics
          </Badge>
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <div className="flex items-center gap-2 text-[11px] text-zinc-500 uppercase tracking-widest">
              <Cpu className="w-3.5 h-3.5" />
              Total Tokens
            </div>
            <div className="text-xl font-mono text-zinc-100 mt-2">{totalTokens.toLocaleString()}</div>
            <div className="text-[11px] text-zinc-600 mt-1">Across {missions.length} missions</div>
          </div>
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <div className="flex items-center gap-2 text-[11px] text-zinc-500 uppercase tracking-widest">
              <DollarSign className="w-3.5 h-3.5" />
              Total Cost
            </div>
            <div className="text-xl font-mono text-zinc-100 mt-2">${(totalCost / 100).toFixed(2)}</div>
            <div className="text-[11px] text-zinc-600 mt-1">ModelProvider • D1 abstraction</div>
          </div>
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <div className="flex items-center gap-2 text-[11px] text-zinc-500 uppercase tracking-widest">
              <Wrench className="w-3.5 h-3.5" />
              Tool Calls
            </div>
            <div className="text-xl font-mono text-zinc-100 mt-2">{totalToolCalls}</div>
            <div className="text-[11px] text-zinc-600 mt-1">{tools.length} tools registered</div>
          </div>
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <div className="flex items-center gap-2 text-[11px] text-zinc-500 uppercase tracking-widest">
              <Activity className="w-3.5 h-3.5" />
              Events
            </div>
            <div className="text-xl font-mono text-zinc-100 mt-2">{events.length}</div>
            <div className="text-[11px] text-zinc-600 mt-1">EventEnvelope scaffold</div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-3">
            <h3 className="text-sm font-medium text-zinc-200 flex items-center gap-2">
              <Bot className="w-4 h-4 text-violet-400" />
              Agent Activity
            </h3>
            <div className="space-y-2">
              {agents.map((agent) => (
                <div key={agent.id} className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-950 border border-zinc-800">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-violet-500" />
                    <span className="text-xs text-zinc-300">{agent.name}</span>
                    <Badge variant="muted" className="text-[9px]">
                      {agent.state}
                    </Badge>
                  </div>
                  <div className="text-[11px] font-mono text-zinc-500">{agent.token_usage} tokens</div>
                </div>
              ))}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-3">
            <h3 className="text-sm font-medium text-zinc-200 flex items-center gap-2">
              <Wrench className="w-4 h-4 text-violet-400" />
              Tool Latency
            </h3>
            <div className="space-y-2">
              {tools
                .filter((t) => t.state === "active")
                .sort((a, b) => b.avg_latency_ms - a.avg_latency_ms)
                .slice(0, 5)
                .map((tool) => (
                  <div key={tool.id} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-300">{tool.name}</span>
                      <span className="font-mono text-zinc-500">{tool.avg_latency_ms}ms</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                      <div className="h-full bg-violet-500" style={{ width: `${Math.min(100, (tool.avg_latency_ms / 1000) * 100)}%` }} />
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-3">
          <h3 className="text-sm font-medium text-zinc-200">Recent Errors • Mock</h3>
          <div className="space-y-2">
            <div className="p-2.5 rounded-lg bg-red-950/20 border border-red-900/30 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <span className="text-xs text-red-300">Tool call failed: shell timeout after 30s • mission-3</span>
              <span className="text-[10px] text-zinc-600 font-mono ml-auto">5m ago</span>
            </div>
            <div className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800 flex items-center gap-2">
              <Clock className="w-4 h-4 text-zinc-500" />
              <span className="text-xs text-zinc-400">Agent Coder waiting for approval 2m • write_file</span>
              <span className="text-[10px] text-zinc-600 font-mono ml-auto">2m ago</span>
            </div>
          </div>
        </div>

        <div className="text-[11px] text-zinc-600 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
          Mock observability • Future: real metrics from agent_runner + tool_registry + ModelProvider token/cost tracking + Postgres storage
        </div>
      </div>
    </AppShell>
  );
}
