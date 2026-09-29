"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X, ShieldAlert, Check, Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MockApproval } from "@/lib/mock/data";

interface ApprovalModalProps {
  approval: MockApproval | null;
  isOpen: boolean;
  onClose: () => void;
  onApprove: (id: string) => void;
  onDeny: (id: string) => void;
}

export function ApprovalModal({ approval, isOpen, onClose, onApprove, onDeny }: ApprovalModalProps) {
  if (!approval) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[95%] max-w-lg rounded-2xl bg-zinc-900 border border-zinc-800 shadow-2xl z-50 overflow-hidden"
          >
            <div className="p-5 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                  <ShieldAlert className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <h3 className="text-sm font-medium text-zinc-100">Approval Required</h3>
                  <p className="text-xs text-zinc-500">{approval.agent_name} • {approval.tool_id}</p>
                </div>
              </div>
              <button onClick={onClose} className="w-8 h-8 rounded-full bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center transition-colors">
                <X className="w-4 h-4 text-zinc-400" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="flex gap-2">
                <Badge variant="warning">{approval.status}</Badge>
                <Badge variant="outline" className="font-mono">
                  {approval.risk_level} risk
                </Badge>
                <Badge variant="muted">{approval.type}</Badge>
              </div>

              <div>
                <div className="text-xs font-medium text-zinc-300 mb-1">Requested Action</div>
                <div className="text-sm text-zinc-100 p-3 rounded-xl bg-zinc-950 border border-zinc-800">{approval.requested_action}</div>
              </div>

              <div>
                <div className="text-xs font-medium text-zinc-300 mb-1">Reasoning</div>
                <div className="text-xs text-zinc-400 leading-relaxed p-3 rounded-xl bg-zinc-950 border border-zinc-800">{approval.reasoning}</div>
              </div>

              <div>
                <div className="text-xs font-medium text-zinc-300 mb-1">Arguments</div>
                <pre className="text-[11px] font-mono text-zinc-400 p-3 rounded-xl bg-zinc-950 border border-zinc-800 overflow-x-auto">
                  {JSON.stringify(approval.args, null, 2)}
                </pre>
              </div>

              <div className="flex gap-3 pt-2">
                <Button onClick={() => onApprove(approval.id)} className="flex-1 h-11 bg-emerald-600 hover:bg-emerald-700 text-white font-medium">
                  <Check className="w-4 h-4 mr-2" />
                  Approve
                </Button>
                <Button onClick={() => onDeny(approval.id)} variant="destructive" className="flex-1 h-11">
                  <Ban className="w-4 h-4 mr-2" />
                  Deny
                </Button>
              </div>

              <p className="text-[10px] text-zinc-600 text-center leading-relaxed">
                Mock approval • Future: approval_service will persist via Postgres + WebSocket EventEnvelope
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
