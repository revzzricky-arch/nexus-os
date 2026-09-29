"use client";

import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Clock, AlertCircle, Pause, Timer } from "lucide-react";
import { MockTask } from "@/lib/mock/data";
import { cn } from "@/lib/utils";

interface TaskProgressProps {
  tasks: MockTask[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function TaskProgress({ tasks, selectedId, onSelect }: TaskProgressProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />;
      case "RUNNING":
        return <Timer className="w-3.5 h-3.5 text-violet-400 animate-pulse" />;
      case "FAILED":
        return <AlertCircle className="w-3.5 h-3.5 text-red-400" />;
      case "QUEUED":
        return <Clock className="w-3.5 h-3.5 text-zinc-500" />;
      case "BLOCKED":
        return <Pause className="w-3.5 h-3.5 text-amber-400" />;
      default:
        return <div className="w-3.5 h-3.5 rounded-full border border-zinc-600" />;
    }
  };

  const getStatusVariant = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "success";
      case "RUNNING":
        return "default";
      case "FAILED":
        return "error";
      case "BLOCKED":
        return "warning";
      default:
        return "muted";
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h4 className="text-[11px] font-medium uppercase tracking-widest text-zinc-500">Task DAG • Layered</h4>
        <span className="text-[10px] text-zinc-600 font-mono">
          {tasks.filter((t) => t.status === "COMPLETED").length}/{tasks.length} completed
        </span>
      </div>

      <div className="space-y-2">
        {tasks.map((task) => {
          const isSelected = selectedId === task.id;
          return (
            <button
              key={task.id}
              onClick={() => onSelect(task.id)}
              className={cn(
                "w-full text-left p-2.5 rounded-xl border transition-all duration-200 flex items-start gap-3",
                isSelected
                  ? "bg-violet-500/10 border-violet-500/30"
                  : "bg-zinc-900 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/80"
              )}
            >
              <div className="mt-0.5">{getStatusIcon(task.status)}</div>
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-zinc-200 truncate">{task.title}</span>
                  <Badge variant={getStatusVariant(task.status) as any} className="text-[9px] px-1.5 py-0 shrink-0">
                    {task.status}
                  </Badge>
                  <span className="text-[10px] text-zinc-600 font-mono">L{task.layer}</span>
                </div>
                <div className="text-[11px] text-zinc-500 line-clamp-1">{task.description}</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1 rounded-full bg-zinc-800 overflow-hidden">
                    <div
                      className="h-full bg-violet-500 transition-all duration-500"
                      style={{ width: `${task.progress}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-zinc-600 font-mono">{task.progress}%</span>
                </div>
                {task.dependencies.length > 0 && (
                  <div className="text-[10px] text-zinc-600 font-mono">deps: {task.dependencies.join(", ")}</div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
