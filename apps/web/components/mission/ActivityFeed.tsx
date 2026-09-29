"use client";

import { Badge } from "@/components/ui/badge";
import { Clock, Bot, Wrench, ShieldCheck, Database, AlertCircle } from "lucide-react";
import { MockEvent } from "@/lib/mock/data";

interface ActivityFeedProps {
  events: MockEvent[];
}

export function ActivityFeed({ events }: ActivityFeedProps) {
  const getEventIcon = (type: string) => {
    if (type.includes("agent")) return <Bot className="w-3 h-3" />;
    if (type.includes("tool")) return <Wrench className="w-3 h-3" />;
    if (type.includes("approval")) return <ShieldCheck className="w-3 h-3" />;
    if (type.includes("memory") || type.includes("rag")) return <Database className="w-3 h-3" />;
    if (type.includes("error")) return <AlertCircle className="w-3 h-3" />;
    return <Clock className="w-3 h-3" />;
  };

  const getEventColor = (type: string) => {
    if (type.includes("completed") || type.includes("success")) return "text-emerald-400";
    if (type.includes("failed") || type.includes("error")) return "text-red-400";
    if (type.includes("approval")) return "text-amber-400";
    if (type.includes("running") || type.includes("started")) return "text-violet-400";
    return "text-zinc-500";
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h4 className="text-[11px] font-medium uppercase tracking-widest text-zinc-500">Live Activity Feed</h4>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-500 font-mono">{events.length} events</span>
      </div>

      <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
        {events.map((event) => (
          <div key={event.id} className="flex gap-2.5 p-2.5 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-colors">
            <div className={`mt-0.5 ${getEventColor(event.type)}`}>{getEventIcon(event.type)}</div>
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium text-zinc-300">{event.type}</span>
                <Badge variant="muted" className="text-[9px] px-1.5 py-0 font-mono">
                  {event.source}
                </Badge>
                <span className="text-[10px] text-zinc-600 font-mono">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className="text-[11px] text-zinc-500 line-clamp-2">
                {event.agent_id && <span className="text-zinc-400">{event.agent_id} • </span>}
                {event.task_id && <span className="text-zinc-400">{event.task_id} • </span>}
                {JSON.stringify(event.payload).slice(0, 80)}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="text-[10px] text-zinc-600 px-1">
        Mock runtime • Future WebSocket EventEnvelope will replace mock with minimal UI changes
      </div>
    </div>
  );
}
