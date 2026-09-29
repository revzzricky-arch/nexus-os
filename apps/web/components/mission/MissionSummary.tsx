"use client";

import { Badge } from "@/components/ui/badge";
import { Clock, Cpu, DollarSign, Bot, Layers } from "lucide-react";
import { MockMission } from "@/lib/mock/data";

interface MissionSummaryProps {
  mission: MockMission;
}

export function MissionSummary({ mission }: MissionSummaryProps) {
  return (
    <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 shadow-soft space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-medium text-zinc-200">Mission Summary</h4>
        <Badge variant="secondary" className="text-[10px] font-mono">
          {mission.progress}% complete
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800">
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 uppercase tracking-widest">
            <Clock className="w-3 h-3" />
            Elapsed
          </div>
          <div className="text-sm font-mono text-zinc-200 mt-1">{Math.floor(mission.elapsed_seconds / 60)}m {mission.elapsed_seconds % 60}s</div>
        </div>
        <div className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800">
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 uppercase tracking-widest">
            <Layers className="w-3 h-3" />
            Tasks
          </div>
          <div className="text-sm font-mono text-zinc-200 mt-1">
            {mission.completed_tasks}/{mission.task_count}
          </div>
        </div>
        <div className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800">
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 uppercase tracking-widest">
            <Cpu className="w-3 h-3" />
            Tokens
          </div>
          <div className="text-sm font-mono text-zinc-200 mt-1">{mission.token_usage.toLocaleString()}</div>
        </div>
        <div className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800">
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 uppercase tracking-widest">
            <DollarSign className="w-3 h-3" />
            Cost
          </div>
          <div className="text-sm font-mono text-zinc-200 mt-1">${(mission.cost_cents / 100).toFixed(2)}</div>
        </div>
      </div>

      <div className="pt-2 border-t border-zinc-800">
        <div className="text-[11px] text-zinc-500">Model Provider • D1</div>
        <div className="text-xs font-mono text-zinc-400 mt-1">OpenAI-compatible (Arena), Anthropic, Ollama — lightweight abstraction</div>
      </div>

      <div className="text-[10px] text-zinc-600 leading-relaxed">
        Mock data • Future phases will show real token/cost from ModelProvider + EmbeddingProvider local-first D2
      </div>
    </div>
  );
}
