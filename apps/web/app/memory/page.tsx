"use client";

import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/badge";
import { Database, Search, Layers } from "lucide-react";

const mockMemory = [
  { id: "mem-1", mission_id: "mission-1", type: "observation", content: "Found 500 errors in API gateway after v0.2.1 deployment", created_at: "2026-09-29T06:02:00Z", agent: "researcher-1" },
  { id: "mem-2", mission_id: "mission-1", type: "decision", content: "Decided to propose fix for gateway error handling", created_at: "2026-09-29T06:05:00Z", agent: "supervisor-1" },
  { id: "mem-3", mission_id: "mission-1", type: "tool_output", content: "web_search results: API gateway 500 errors common causes", created_at: "2026-09-29T06:02:45Z", agent: "researcher-1" },
  { id: "mem-4", mission_id: "mission-2", type: "synthesis", content: "Top 5 frameworks: LangGraph, CrewAI, AutoGen, OpenAI Swarm, LlamaIndex", created_at: "2026-09-28T15:00:00Z", agent: "analyst-1" },
];

export default function MemoryPage() {
  return (
    <AppShell>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-zinc-100 tracking-tight">Memory</h1>
            <p className="text-sm text-zinc-500 mt-1">Shared mission memory • RAG • Local-first embedding • Mock</p>
          </div>
          <Badge variant="secondary" className="font-mono">
            {mockMemory.length} entries • 128 total
          </Badge>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <div className="flex items-center gap-2 text-[11px] text-zinc-500 uppercase tracking-widest">
              <Database className="w-3.5 h-3.5" />
              Collections
            </div>
            <div className="text-xl font-mono text-zinc-100 mt-2">3</div>
            <div className="text-[11px] text-zinc-600 mt-1">missions, tools, docs • pgvector future</div>
          </div>
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <div className="flex items-center gap-2 text-[11px] text-zinc-500 uppercase tracking-widest">
              <Search className="w-3.5 h-3.5" />
              Embedding
            </div>
            <div className="text-xl font-mono text-zinc-100 mt-2">Local-first</div>
            <div className="text-[11px] text-zinc-600 mt-1">D2 • replaceable later • abstract pulse in 3D</div>
          </div>
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <div className="flex items-center gap-2 text-[11px] text-zinc-500 uppercase tracking-widest">
              <Layers className="w-3.5 h-3.5" />
              RAG Query
            </div>
            <div className="text-xl font-mono text-zinc-100 mt-2">34 calls</div>
            <div className="text-[11px] text-zinc-600 mt-1">Mock • Future real rag_query tool</div>
          </div>
        </div>

        <div className="space-y-3">
          <h3 className="text-sm font-medium text-zinc-200">Recent Memory Entries • Mock</h3>
          <div className="space-y-2">
            {mockMemory.map((entry) => (
              <div key={entry.id} className="p-3 rounded-xl bg-zinc-900 border border-zinc-800">
                <div className="flex items-center gap-2">
                  <Badge variant="muted" className="text-[10px] font-mono">
                    {entry.type}
                  </Badge>
                  <span className="text-[11px] text-zinc-500">{entry.agent} • {entry.mission_id}</span>
                  <span className="text-[10px] text-zinc-600 font-mono ml-auto">{new Date(entry.created_at).toLocaleString()}</span>
                </div>
                <div className="text-xs text-zinc-300 mt-2 leading-relaxed">{entry.content}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="text-[11px] text-zinc-600 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50 leading-relaxed">
          Mock memory • Future: real memory service with Postgres + pgvector, EmbeddingProvider local-first D2, memory_search tool, RAG collections, not rendered as raw 3D nodes per architecture (runtime focus only).
        </div>
      </div>
    </AppShell>
  );
}
