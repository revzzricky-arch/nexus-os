"use client";

import { Badge } from "@/components/ui/badge";
import { Clock, Layers, Bot, Activity, Timer } from "lucide-react";
import { MockMission } from "@/lib/mock/data";

interface MissionHeaderProps {
  mission: MockMission;
}

export function MissionHeader({ mission }: MissionHeaderProps) {
  const formatElapsed = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

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
    <div className="px-4 md:px-6 py-4 border-b border-zinc-800/80 bg-zinc-900/20 backdrop-blur-sm">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-2 min-w-0 flex-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h2 className="text-lg font-semibold text-zinc-100 tracking-tight truncate">{mission.title}</h2>
            <Badge variant={getStatusVariant(mission.status) as any} className="shrink-0">
              {mission.status}
            </Badge>
            <Badge variant="outline" className="shrink-0 font-mono text-[11px]">
              {mission.type}
            </Badge>
          </div>
          <p className="text-sm text-zinc-400 line-clamp-2 max-w-3xl">{mission.goal}</p>
        </div>

        <div className="flex items-center gap-3 flex-wrap lg:shrink-0">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-900 border border-zinc-800">
            <Timer className="w-3.5 h-3.5 text-zinc-500" />
            <span className="text-xs text-zinc-400 font-mono">{formatElapsed(mission.elapsed_seconds)}</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-900 border border-zinc-800">
            <Activity className="w-3.5 h-3.5 text-zinc-500" />
            <span className="text-xs text-zinc-400">{mission.phase}</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-900 border border-zinc-800">
            <Bot className="w-3.5 h-3.5 text-zinc-500" />
            <span className="text-xs text-zinc-400">{mission.agent_count} agents</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-900 border border-zinc-800">
            <Layers className="w-3.5 h-3.5 text-zinc-500" />
            <span className="text-xs text-zinc-400">
              {mission.completed_tasks}/{mission.task_count}
            </span>
          </div>
          <div className="w-full lg:w-24 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div className="h-full bg-violet-500 transition-all duration-500" style={{ width: `${mission.progress}%` }} />
          </div>
        </div>
      </div>
    </div>
  );
}
