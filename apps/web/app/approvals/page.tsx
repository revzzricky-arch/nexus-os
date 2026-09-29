"use client";

import { AppShell } from "@/components/layout/AppShell";
import { useRuntimeStore } from "@/lib/store/runtime";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ShieldCheck, Clock, AlertTriangle } from "lucide-react";

export default function ApprovalsPage() {
  const approvals = useRuntimeStore((s) => s.approvals);
  const approve = useRuntimeStore((s) => s.approveApproval);
  const deny = useRuntimeStore((s) => s.denyApproval);
  const pending = approvals.filter((a) => a.status === "PENDING");

  return (
    <AppShell>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-zinc-100 tracking-tight">Approvals</h1>
            <p className="text-sm text-zinc-500 mt-1">Balanced policy • Shell always approval • D6</p>
          </div>
          <Badge variant={pending.length > 0 ? "warning" : "secondary"} className="font-mono">
            {pending.length} pending
          </Badge>
        </div>

        <div className="grid gap-4">
          {approvals.map((approval) => (
            <div
              key={approval.id}
              className={`p-4 rounded-xl border transition-colors ${
                approval.status === "PENDING" ? "bg-amber-950/10 border-amber-900/30" : "bg-zinc-900 border-zinc-800"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                    <ShieldCheck className="w-5 h-5 text-amber-400" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-zinc-100">{approval.requested_action}</div>
                    <div className="text-xs text-zinc-500">
                      {approval.agent_name} • {approval.tool_id} • {new Date(approval.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Badge variant={approval.status === "PENDING" ? "warning" : approval.status === "APPROVED" ? "success" : "error"}>
                    {approval.status}
                  </Badge>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {approval.risk_level}
                  </Badge>
                </div>
              </div>

              <div className="mt-3 space-y-3">
                <div className="text-xs text-zinc-400 leading-relaxed p-3 rounded-xl bg-zinc-950 border border-zinc-800">
                  {approval.reasoning}
                </div>

                <pre className="text-[11px] font-mono text-zinc-500 p-3 rounded-xl bg-zinc-950 border border-zinc-800 overflow-x-auto">
                  {JSON.stringify(approval.args, null, 2)}
                </pre>

                {approval.status === "PENDING" ? (
                  <div className="flex gap-2">
                    <Button onClick={() => approve(approval.id)} className="flex-1 h-9 bg-emerald-600 hover:bg-emerald-700 text-white">
                      Approve
                    </Button>
                    <Button onClick={() => deny(approval.id)} variant="destructive" className="flex-1 h-9">
                      Deny
                    </Button>
                  </div>
                ) : (
                  <div className="text-[11px] text-zinc-600">Decision: {approval.status} • Mock persistence • Future Postgres</div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="text-[11px] text-zinc-600 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50 leading-relaxed">
          D6 Balanced approval policy: shell always requires approval, write_file high-risk requires approval, low-risk auto. 3D approval gates are hexagonal, click opens this UI. Future: approval_service with WebSocket EventEnvelope approval_requested / approval_decided.
        </div>
      </div>
    </AppShell>
  );
}
