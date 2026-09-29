"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X, Bot, Layers, ShieldCheck, Cpu, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MockAgent, MockTask, MockApproval } from "@/lib/mock/data";

interface DetailPanelProps {
  agent: MockAgent | null;
  task: MockTask | null;
  approval: MockApproval | null;
  onClose: () => void;
  onApprove?: (id: string) => void;
  onDeny?: (id: string) => void;
}

export function DetailPanel({ agent, task, approval, onClose, onApprove, onDeny }: DetailPanelProps) {
  const hasContent = agent || task || approval;

  return (
    <AnimatePresence>
      {hasContent && (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 20 }}
          className="w-full lg:w-[360px] shrink-0 border-l border-zinc-800 bg-zinc-950/50 backdrop-blur-xl flex flex-col max-h-[calc(100vh-49px)] overflow-hidden"
        >
          <div className="flex items-center justify-between p-4 border-b border-zinc-800">
            <h3 className="text-sm font-medium text-zinc-200 flex items-center gap-2">
              {agent && <Bot className="w-4 h-4 text-violet-400" />}
              {task && <Layers className="w-4 h-4 text-violet-400" />}
              {approval && <ShieldCheck className="w-4 h-4 text-amber-400" />}
              {agent ? "Agent Details" : task ? "Task Details" : "Approval Details"}
            </h3>
            <button onClick={onClose} className="w-7 h-7 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center hover:bg-zinc-800 transition-colors">
              <X className="w-3.5 h-3.5 text-zinc-400" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {agent && (
              <>
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
                      <Bot className="w-5 h-5 text-violet-400" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-zinc-100">{agent.name}</div>
                      <div className="text-xs text-zinc-500">{agent.role}</div>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Badge variant={agent.state === "RUNNING" ? "default" : agent.state === "WAITING_FOR_APPROVAL" ? "warning" : "secondary"}>
                      {agent.state}
                    </Badge>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {agent.type}
                    </Badge>
                  </div>

                  <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 space-y-2">
                    <div className="text-[11px] text-zinc-500 uppercase tracking-widest">Current Task</div>
                    <div className="text-sm text-zinc-200">{agent.current_task_title || "Idle"}</div>
                    <div className="text-xs text-zinc-500 leading-relaxed">{agent.recent_activity}</div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800">
                      <div className="text-[10px] text-zinc-500 flex items-center gap-1">
                        <Cpu className="w-3 h-3" /> TOKENS
                      </div>
                      <div className="text-sm font-mono text-zinc-200 mt-1">{agent.token_usage}</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800">
                      <div className="text-[10px] text-zinc-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" /> COST
                      </div>
                      <div className="text-sm font-mono text-zinc-200 mt-1">${(agent.cost_cents / 100).toFixed(2)}</div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-[11px] text-zinc-500 uppercase tracking-widest">Capabilities</div>
                    <div className="flex flex-wrap gap-1.5">
                      {agent.capabilities.map((cap) => (
                        <Badge key={cap} variant="muted" className="text-[10px] font-mono">
                          {cap}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-[11px] text-zinc-500 uppercase tracking-widest">Model</div>
                    <div className="text-xs font-mono text-zinc-400 p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                      {agent.provider} • {agent.model}
                    </div>
                  </div>
                </div>

                <div className="text-[10px] text-zinc-600 leading-relaxed p-2 rounded-lg bg-zinc-900/50 border border-zinc-800/50">
                  Future: Real agent logs will stream via WebSocket EventEnvelope — this panel will show live tool calls and reasoning.
                </div>
              </>
            )}

            {task && (
              <>
                <div className="space-y-3">
                  <div className="text-sm font-medium text-zinc-100">{task.title}</div>
                  <div className="text-xs text-zinc-500 leading-relaxed">{task.description}</div>

                  <div className="flex gap-2">
                    <Badge
                      variant={
                        task.status === "RUNNING" ? "default" : task.status === "COMPLETED" ? "success" : task.status === "FAILED" ? "error" : "secondary"
                      }
                    >
                      {task.status}
                    </Badge>
                    <Badge variant="outline">Layer {task.layer}</Badge>
                    <Badge variant="muted" className="font-mono">
                      {task.agent_type}
                    </Badge>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-[11px] text-zinc-500">
                      <span>Progress</span>
                      <span className="font-mono">{task.progress}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                      <div className="h-full bg-violet-500 transition-all" style={{ width: `${task.progress}%` }} />
                    </div>
                  </div>

                  {task.dependencies.length > 0 && (
                    <div className="space-y-1">
                      <div className="text-[11px] text-zinc-500 uppercase tracking-widest">Dependencies</div>
                      <div className="flex flex-wrap gap-1">
                        {task.dependencies.map((dep) => (
                          <Badge key={dep} variant="muted" className="text-[10px] font-mono">
                            {dep}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {task.output && (
                    <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800">
                      <div className="text-[11px] text-zinc-500 uppercase tracking-widest mb-1">Output</div>
                      <div className="text-xs text-zinc-400 font-mono">{task.output}</div>
                    </div>
                  )}

                  <div className="text-[11px] text-zinc-600">Agent: {task.agent_id || "unassigned"}</div>
                </div>
              </>
            )}

            {approval && (
              <>
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge variant={approval.status === "PENDING" ? "warning" : approval.status === "APPROVED" ? "success" : "error"}>
                      {approval.status}
                    </Badge>
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {approval.risk_level} risk
                    </Badge>
                    <Badge variant="muted">{approval.type}</Badge>
                  </div>

                  <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-900/30 space-y-2">
                    <div className="text-xs font-medium text-amber-200">{approval.requested_action}</div>
                    <div className="text-[11px] text-amber-200/70 leading-relaxed">{approval.reasoning}</div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-[11px] text-zinc-500 uppercase tracking-widest">Tool Args</div>
                    <pre className="text-[11px] font-mono text-zinc-400 p-3 rounded-xl bg-zinc-900 border border-zinc-800 overflow-x-auto">
                      {JSON.stringify(approval.args, null, 2)}
                    </pre>
                  </div>

                  <div className="text-[11px] text-zinc-500">
                    Agent: {approval.agent_name} • Tool: {approval.tool_id}
                  </div>

                  {approval.status === "PENDING" && onApprove && onDeny && (
                    <div className="flex gap-2 pt-2">
                      <Button onClick={() => onApprove(approval.id)} className="flex-1 h-9 bg-emerald-600 hover:bg-emerald-700 text-white">
                        Approve
                      </Button>
                      <Button onClick={() => onDeny(approval.id)} variant="destructive" className="flex-1 h-9">
                        Deny
                      </Button>
                    </div>
                  )}

                  <div className="text-[10px] text-zinc-600 leading-relaxed">
                    D6 Balanced approval policy: shell always requires approval, write_file high-risk requires approval. Future: real approval_service will enforce via WebSocket.
                  </div>
                </div>
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
