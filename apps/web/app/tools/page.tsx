"use client";

import { AppShell } from "@/components/layout/AppShell";
import { useRuntimeStore } from "@/lib/store/runtime";
import { Badge } from "@/components/ui/badge";
import { Wrench, Plug, Clock, AlertTriangle } from "lucide-react";

export default function ToolsPage() {
  const tools = useRuntimeStore((s) => s.tools);

  const getRiskVariant = (risk: string) => {
    switch (risk) {
      case "low":
        return "success";
      case "medium":
        return "secondary";
      case "high":
        return "warning";
      case "critical":
        return "error";
      default:
        return "muted";
    }
  };

  const getPermVariant = (perm: string) => {
    switch (perm) {
      case "auto":
        return "success";
      case "approval_required":
        return "warning";
      case "forbidden":
        return "error";
      default:
        return "muted";
    }
  };

  return (
    <AppShell>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-zinc-100 tracking-tight">Tools / MCP</h1>
            <p className="text-sm text-zinc-500 mt-1">Registry • SandboxService • stdio + Streamable HTTP • SSE legacy only</p>
          </div>
          <Badge variant="secondary" className="font-mono">
            {tools.length} tools • {tools.filter((t) => t.source === "mcp").length} MCP
          </Badge>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {tools.map((tool) => (
            <div key={tool.id} className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-700 transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center">
                    {tool.source === "mcp" ? <Plug className="w-4 h-4 text-violet-400" /> : <Wrench className="w-4 h-4 text-zinc-400" />}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-zinc-100 flex items-center gap-2">
                      {tool.name}
                      <Badge variant={tool.state === "active" ? "success" : "secondary"} className="text-[9px]">
                        {tool.state}
                      </Badge>
                    </div>
                    <div className="text-xs text-zinc-500">{tool.description}</div>
                  </div>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                <Badge variant="muted" className="font-mono text-[10px]">
                  {tool.source}
                </Badge>
                {tool.mcp_transport && (
                  <Badge variant={tool.mcp_transport === "sse_legacy" ? "error" : "secondary"} className="text-[10px] font-mono">
                    {tool.mcp_transport}
                  </Badge>
                )}
                <Badge variant={getRiskVariant(tool.risk_level) as any} className="text-[10px]">
                  {tool.risk_level} risk
                </Badge>
                <Badge variant={getPermVariant(tool.permission) as any} className="text-[10px]">
                  {tool.permission}
                </Badge>
              </div>

              <div className="mt-3 flex items-center gap-3 text-[11px] text-zinc-600 font-mono">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {tool.avg_latency_ms}ms avg
                </span>
                <span>•</span>
                <span>{tool.call_count} calls</span>
                {tool.permission === "approval_required" && (
                  <>
                    <span>•</span>
                    <span className="flex items-center gap-1 text-amber-400">
                      <AlertTriangle className="w-3 h-3" />
                      approval
                    </span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="grid gap-3 md:grid-cols-2 text-[11px] text-zinc-600">
          <div className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
            <div className="text-zinc-400 font-medium mb-1">MCP Transport • D per constraints</div>
            Use stdio for local MCP servers, Streamable HTTP for remote. SSE may be mentioned only as legacy compatibility. Here legacy-sse tool is forbidden.
          </div>
          <div className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
            <div className="text-zinc-400 font-medium mb-1">SandboxService • Abstraction</div>
            MVP uses container isolation where command execution required. Agents never receive unrestricted host shell/file access. Tool calls via SandboxService, not direct fs.
          </div>
        </div>
      </div>
    </AppShell>
  );
}
