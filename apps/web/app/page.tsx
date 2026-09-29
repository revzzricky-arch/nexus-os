"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { motion } from "framer-motion";

// Dynamic import for 3D canvas - no SSR
const MissionCanvas = dynamic(() => import("@/components/3d/Scene"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-zinc-900/50 rounded-xl border border-zinc-800">
      <div className="text-center space-y-3">
        <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mx-auto" />
        <p className="text-sm text-zinc-400">Initializing 3D Runtime...</p>
      </div>
    </div>
  ),
});

export default function DashboardPage() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [is3DEnabled, setIs3DEnabled] = useState(true);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top Status Bar - dark futuristic */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-zinc-900/80 border-b border-zinc-800">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center">
                <span className="text-white font-bold text-sm">N</span>
              </div>
              <div>
                <h1 className="font-semibold text-zinc-100 tracking-tight">NEXUS</h1>
                <p className="text-[10px] text-zinc-500 -mt-1 tracking-widest uppercase">Codename • Public name TBD</p>
              </div>
            </div>
            <div className="h-6 w-px bg-zinc-800 hidden md:block" />
            <div className="hidden md:flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-subtle" />
              <span className="text-xs text-zinc-400">Scaffold • Docker Compose MVP</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-800/50 border border-zinc-700/50">
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest">API</span>
              <span className="text-xs text-emerald-400">●</span>
              <span className="text-xs text-zinc-300">/health ok</span>
            </div>
            <div className="px-3 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/20">
              <span className="text-xs text-violet-300">v0.1.0-scaffold</span>
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col lg:flex-row">
        {/* Sidebar - navigation */}
        <aside className="w-full lg:w-[280px] border-b lg:border-b-0 lg:border-r border-zinc-800 bg-zinc-900/30 backdrop-blur-sm">
          <div className="p-4 space-y-6">
            {/* Navigation */}
            <nav className="space-y-1">
              <div className="text-[10px] text-zinc-500 uppercase tracking-widest px-3 py-2">Mission Control</div>
              {[
                { name: "Dashboard", active: true, icon: "◈" },
                { name: "Missions", active: false, count: 0 },
                { name: "Agents", active: false, count: 4 },
                { name: "Tools", active: false, count: 8 },
                { name: "Approvals", active: false, count: 0, highlight: true },
              ].map((item) => (
                <div
                  key={item.name}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                    item.active
                      ? "bg-violet-500/10 text-violet-200 border border-violet-500/20"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
                  }`}
                >
                  <span className="flex items-center gap-2">
                    {item.icon && <span className="text-violet-400">{item.icon}</span>}
                    {item.name}
                  </span>
                  {item.count !== undefined && (
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        item.highlight
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-zinc-800 text-zinc-500"
                      }`}
                    >
                      {item.count}
                    </span>
                  )}
                </div>
              ))}
            </nav>

            <div className="space-y-3">
              <div className="text-[10px] text-zinc-500 uppercase tracking-widest px-3">Runtime</div>
              <div className="space-y-2 px-3">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500">Missions</span>
                  <span className="text-zinc-300">0 active</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500">Agents</span>
                  <span className="text-zinc-300">3 scaffold</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500">Model Provider</span>
                  <span className="text-zinc-400">placeholder</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500">Embedding</span>
                  <span className="text-zinc-400">local-first</span>
                </div>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 space-y-2">
              <div className="text-xs font-medium text-zinc-200">Scaffold Status</div>
              <p className="text-[11px] text-zinc-500 leading-relaxed">
                This is a scaffold and 3D prototype. Real agent orchestration, MCP, RAG, memory, approvals, and model integrations are not implemented yet. See docs/architecture.md v0.2.
              </p>
              <div className="flex gap-1.5 pt-1">
                <span className="text-[9px] px-2 py-1 rounded-full bg-zinc-800 text-zinc-500">D1 ModelProvider</span>
                <span className="text-[9px] px-2 py-1 rounded-full bg-zinc-800 text-zinc-500">D5 Hybrid 3D</span>
              </div>
            </div>

            <div className="text-[10px] text-zinc-600 px-3 space-y-1">
              <div>Decisions: D1 custom ModelProvider, D2 local embedding, D3 pnpm, D4 Bearer token, D5 hybrid 3D, D6 balanced approval, D7 Docker Compose, D8 codename, D9 MIT, D10 scaffold first</div>
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 flex flex-col">
          {/* Mission Area + 3D */}
          <div className="flex-1 grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-0">
            {/* 3D Runtime Prototype */}
            <div className="relative h-[500px] xl:h-auto xl:min-h-[600px] border-b xl:border-b-0 xl:border-r border-zinc-800 bg-zinc-950/50">
              <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <h2 className="text-sm font-medium text-zinc-200">Mission Runtime — 3D Prototype</h2>
                  <span className="text-[10px] px-2 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-300">
                    Hybrid Orbital + Layered DAG
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setIs3DEnabled(!is3DEnabled)}
                    className="text-[11px] px-3 py-1 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
                  >
                    {is3DEnabled ? "Disable 3D" : "Enable 3D"}
                  </button>
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                </div>
              </div>

              <div className="absolute inset-0 pt-[60px]">
                {is3DEnabled ? (
                  <MissionCanvas selectedAgent={selectedAgent} onSelectAgent={setSelectedAgent} />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <div className="text-center space-y-2">
                      <p className="text-sm text-zinc-500">3D disabled — showing 2D fallback</p>
                      <p className="text-xs text-zinc-600">Mobile fallback per architecture</p>
                    </div>
                  </div>
                )}
              </div>

              {/* 3D Overlay Stats */}
              <div className="absolute bottom-4 left-4 right-4 flex justify-between items-end pointer-events-none">
                <div className="flex gap-2">
                  <div className="px-2.5 py-1.5 rounded-lg bg-zinc-900/80 backdrop-blur border border-zinc-800 text-[11px] text-zinc-400">
                    <span className="text-zinc-500">Agents:</span> 3 scaffold
                  </div>
                  <div className="px-2.5 py-1.5 rounded-lg bg-zinc-900/80 backdrop-blur border border-zinc-800 text-[11px] text-zinc-400">
                    <span className="text-zinc-500">Tasks:</span> 3 layered
                  </div>
                  <div className="px-2.5 py-1.5 rounded-lg bg-zinc-900/80 backdrop-blur border border-zinc-800 text-[11px] text-zinc-400">
                    <span className="text-zinc-500">Focus:</span> runtime only
                  </div>
                </div>
                <div className="hidden md:block px-2.5 py-1.5 rounded-lg bg-zinc-900/80 backdrop-blur border border-zinc-800 text-[10px] text-zinc-500">
                  Drag to orbit • Scroll to zoom • Click agent to select
                </div>
              </div>
            </div>

            {/* Activity Panel - placeholder */}
            <div className="bg-zinc-900/20 backdrop-blur-sm">
              <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
                <h3 className="text-sm font-medium text-zinc-200">Activity & Details</h3>
                <span className="text-[10px] px-2 py-1 rounded-full bg-zinc-800 text-zinc-500">Scaffold</span>
              </div>

              <div className="p-4 space-y-6">
                {/* Selected Agent */}
                <div className="space-y-3">
                  <h4 className="text-[11px] uppercase tracking-widest text-zinc-500">Selected Agent</h4>
                  {selectedAgent ? (
                    <motion.div
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="p-3 rounded-xl bg-violet-500/5 border border-violet-500/20"
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center">
                          <span className="text-violet-300 text-xs">●</span>
                        </div>
                        <div>
                          <div className="text-sm text-zinc-200">{selectedAgent}</div>
                          <div className="text-[11px] text-zinc-500">running • tool_calling</div>
                        </div>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
                        <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                          <div className="text-zinc-500">Tokens</div>
                          <div className="text-zinc-300">1,234</div>
                        </div>
                        <div className="p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                          <div className="text-zinc-500">Cost</div>
                          <div className="text-zinc-300">$0.04</div>
                        </div>
                      </div>
                    </motion.div>
                  ) : (
                    <div className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800 border-dashed">
                      <p className="text-xs text-zinc-500">Click an agent node in 3D to inspect</p>
                      <p className="text-[11px] text-zinc-600 mt-1">Runtime state only, no vector DB nodes</p>
                    </div>
                  )}
                </div>

                {/* Mission Placeholder */}
                <div className="space-y-3">
                  <h4 className="text-[11px] uppercase tracking-widest text-zinc-500">Mission Placeholder</h4>
                  <div className="space-y-2">
                    {[
                      { title: "Research top 5 agent frameworks", agent: "researcher", status: "running", color: "violet" },
                      { title: "Analyze features", agent: "analyst", status: "queued", color: "zinc" },
                      { title: "Write report", agent: "coder", status: "pending", color: "zinc" },
                    ].map((task, i) => (
                      <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-900 border border-zinc-800">
                        <div className={`w-1.5 h-1.5 rounded-full ${task.status === "running" ? "bg-violet-500 animate-pulse" : "bg-zinc-600"}`} />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-zinc-300 truncate">{task.title}</div>
                          <div className="text-[10px] text-zinc-500">{task.agent} • {task.status}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Tool Activity Placeholder */}
                <div className="space-y-3">
                  <h4 className="text-[11px] uppercase tracking-widest text-zinc-500">Tool Activity (Runtime)</h4>
                  <div className="space-y-2">
                    <div className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-zinc-300">web_search</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300">success</span>
                      </div>
                      <div className="text-[10px] text-zinc-500 mt-1">via SandboxService • no host exec</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-zinc-300">rag_query</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-300">running</span>
                      </div>
                      <div className="text-[10px] text-zinc-500 mt-1">local-first embedding • abstract pulse on core</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-zinc-900 border border-amber-500/20">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-zinc-300">write_file</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300">approval</span>
                      </div>
                      <div className="text-[10px] text-zinc-500 mt-1">balanced policy • approval gate in 3D</div>
                    </div>
                  </div>
                </div>

                {/* Event Contract */}
                <div className="space-y-2">
                  <h4 className="text-[11px] uppercase tracking-widest text-zinc-500">Event Contract (Scaffold)</h4>
                  <pre className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-[10px] text-zinc-400 overflow-x-auto">
{`{
  id: "evt_...",
  timestamp: "2026-09-29T...",
  mission_id: "uuid",
  type: "agent_state_changed",
  source: "agent_runner",
  payload: { from, to }
}`}
                  </pre>
                  <p className="text-[10px] text-zinc-600">No Redis/WS streaming yet, contract only. WS auth via initial message, not ?token= in URL.</p>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Status */}
          <div className="border-t border-zinc-800 bg-zinc-900/30 backdrop-blur-sm px-6 py-3 flex flex-col md:flex-row justify-between gap-2 text-[11px] text-zinc-500">
            <div className="flex items-center gap-4">
              <span>Frontend: Next.js 16.x + React 19 + R3F 9 + Drei</span>
              <span className="hidden md:inline">•</span>
              <span>Backend: FastAPI • /health ok • /version ok</span>
              <span className="hidden md:inline">•</span>
              <span>Docker: postgres+pgvector, redis, web, api</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-1 rounded-full bg-zinc-800 text-zinc-400">Scaffold Phase</span>
              <span>Limitations: No real agents, MCP, RAG, LLM calls yet</span>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
