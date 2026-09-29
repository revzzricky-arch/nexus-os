"use client";

import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Bot, Cpu, Clock, Zap, AlertTriangle } from "lucide-react";
import { MockAgent } from "@/lib/mock/data";
import { cn } from "@/lib/utils";

interface AgentCardsProps {
  agents: MockAgent[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function AgentCards({ agents, selectedId, onSelect }: AgentCardsProps) {
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

  const getStateIcon = (state: string) => {
    switch (state) {
      case "RUNNING":
        return <Zap className="w-3 h-3" />;
      case "WAITING_FOR_APPROVAL":
        return <AlertTriangle className="w-3 h-3" />;
      case "COMPLETED":
        return <span className="text-[10px]">✓</span>;
      default:
        return <Clock className="w-3 h-3" />;
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h4 className="text-[11px] font-medium uppercase tracking-widest text-zinc-500">Agents</h4>
        <span className="text-[10px] text-zinc-600 font-mono">{agents.length} • 4 types</span>
      </div>

      <div className="grid gap-2">
        {agents.map((agent) => {
          const isSelected = selectedId === agent.id;
          return (
            <motion.button
              key={agent.id}
              onClick={() => onSelect(agent.id)}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              className={cn(
                "w-full text-left p-3 rounded-xl border transition-all duration-200",
                isSelected
                  ? "bg-violet-500/10 border-violet-500/30 shadow-soft"
                  : "bg-zinc-900 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/80"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <div
                    className={cn(
                      "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
                      agent.type === "supervisor"
                        ? "bg-violet-500/15 border border-violet-500/20"
                        : agent.type === "researcher"
                        ? "bg-cyan-500/10 border border-cyan-500/20"
                        : agent.type === "coder"
                        ? "bg-amber-500/10 border border-amber-500/20"
                        : "bg-emerald-500/10 border border-emerald-500/20"
                    )}
                  >
                    <Bot className="w-4 h-4 text-zinc-300" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-200 truncate">{agent.name}</span>
                      <Badge variant={getStateVariant(agent.state) as any} className="text-[9px] px-1.5 py-0 flex items-center gap-1">
                        {getStateIcon(agent.state)}
                        {agent.state}
                      </Badge>
                    </div>
                    <div className="text-[11px] text-zinc-500 truncate">{agent.role}</div>
                  </div>
                </div>
              </div>

              <div className="mt-2.5 space-y-1.5">
                <div className="text-xs text-zinc-300 truncate">
                  <span className="text-zinc-500">Task:</span> {agent.current_task_title || "Idle"}
                </div>
                <div className="text-[11px] text-zinc-500 line-clamp-2 leading-relaxed">{agent.recent_activity}</div>
              </div>

              <div className="mt-2.5 flex items-center justify-between">
                <div className="flex items-center gap-2 text-[10px] text-zinc-600 font-mono">
                  <span className="flex items-center gap-1">
                    <Cpu className="w-3 h-3" />
                    {agent.token_usage}
                  </span>
                  <span>•</span>
                  <span>${(agent.cost_cents / 100).toFixed(2)}</span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-500 font-mono">{agent.model}</span>
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
