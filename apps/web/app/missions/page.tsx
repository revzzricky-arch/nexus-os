"use client";

import { AppShell } from "@/components/layout/AppShell";
import { useRuntimeStore } from "@/lib/store/runtime";
import { Badge } from "@/components/ui/badge";
import { formatElapsed } from "@/lib/utils";
import { Clock, Bot, Layers, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function MissionsPage() {
  const missions = useRuntimeStore((s) => s.missions);
  const setActiveMission = useRuntimeStore((s) => s.setActiveMission);

  const getStatusVariant = (status: string) => {
    switch (status) {
      case "running":
        return "default";
      case "completed":
        return "success";
      case "awaiting_approval":
        return "warning";
      case "failed":
        return "error";
      case "paused":
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
            <h1 className="text-xl font-semibold text-zinc-100 tracking-tight">Missions</h1>
            <p className="text-sm text-zinc-500 mt-1">Manage and monitor all missions • Mock runtime</p>
          </div>
          <Badge variant="secondary" className="font-mono">
            {missions.length} total
          </Badge>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {missions.map((mission) => (
            <div
              key={mission.id}
              className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-colors group"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-medium text-zinc-100 truncate">{mission.title}</h3>
                    <Badge variant={getStatusVariant(mission.status) as any} className="shrink-0">
                      {mission.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{mission.goal}</p>
                </div>
                <Badge variant="outline" className="font-mono text-[10px] shrink-0">
                  {mission.type}
                </Badge>
              </div>

              <div className="mt-3 space-y-3">
                <div className="flex items-center gap-3 text-[11px] text-zinc-500">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatElapsed(mission.elapsed_seconds)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Bot className="w-3 h-3" />
                    {mission.agent_count} agents
                  </span>
                  <span className="flex items-center gap-1">
                    <Layers className="w-3 h-3" />
                    {mission.completed_tasks}/{mission.task_count}
                  </span>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-zinc-500">
                    <span>Progress</span>
                    <span className="font-mono">{mission.progress}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                    <div className="h-full bg-violet-500 transition-all" style={{ width: `${mission.progress}%` }} />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-[10px] text-zinc-600 font-mono">{new Date(mission.created_at).toLocaleString()}</span>
                  <Link href="/" onClick={() => setActiveMission(mission)}>
                    <button className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 transition-colors">
                      Open <ArrowRight className="w-3 h-3" />
                    </button>
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="text-[11px] text-zinc-600 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
          Mock data • Future: real missions from Postgres via API + WebSocket EventEnvelope
        </div>
      </div>
    </AppShell>
  );
}
