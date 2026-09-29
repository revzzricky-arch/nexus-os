"use client";

import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useState } from "react";

export default function SettingsPage() {
  const [modelProvider, setModelProvider] = useState("openai-compatible");
  const [embedding, setEmbedding] = useState("local-first");
  const [bearer, setBearer] = useState("Bearer dev-token");

  return (
    <AppShell>
      <div className="p-6 space-y-6 max-w-3xl">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100 tracking-tight">Settings</h1>
          <p className="text-sm text-zinc-500 mt-1">Model provider placeholders • Appearance • Runtime • Security • Dev config • Mock only</p>
        </div>

        <div className="space-y-6">
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-zinc-200">Model Provider • D1</h3>
              <Badge variant="secondary" className="text-[10px]">
                Abstraction
              </Badge>
            </div>
            <div className="grid gap-4">
              <div className="space-y-2">
                <label className="text-xs text-zinc-400">Provider</label>
                <select
                  value={modelProvider}
                  onChange={(e) => setModelProvider(e.target.value)}
                  className="w-full h-10 px-3 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-300"
                >
                  <option value="openai-compatible">OpenAI-compatible (Arena)</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="ollama">Ollama</option>
                </select>
                <p className="text-[11px] text-zinc-600">Lightweight abstraction ModelProvider with OpenAI-compatible, Anthropic, Ollama providers. Arena/OpenAI-compatible must fit behind abstraction.</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                  <div className="text-[11px] text-zinc-500 uppercase tracking-widest">Model</div>
                  <div className="text-xs font-mono text-zinc-300 mt-1">gpt-4o-mini • placeholder</div>
                </div>
                <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                  <div className="text-[11px] text-zinc-500 uppercase tracking-widest">API Base</div>
                  <div className="text-xs font-mono text-zinc-300 mt-1">https://api.arena... • mock</div>
                </div>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-zinc-200">Embedding Provider • D2</h3>
              <Badge variant="secondary" className="text-[10px]">
                Local-first
              </Badge>
            </div>
            <div className="space-y-2">
              <label className="text-xs text-zinc-400">Embedding</label>
              <select
                value={embedding}
                onChange={(e) => setEmbedding(e.target.value)}
                className="w-full h-10 px-3 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-300"
              >
                <option value="local-first">Local-first • replaceable later</option>
                <option value="openai">OpenAI embedding • future</option>
              </select>
              <p className="text-[11px] text-zinc-600">D2 local embedding first, replaceable later. RAG collections use local-first, abstract pulse on MissionCore in 3D.</p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
            <h3 className="text-sm font-medium text-zinc-200">Appearance</h3>
            <div className="grid gap-3">
              <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <div>
                  <div className="text-xs text-zinc-300">Theme</div>
                  <div className="text-[11px] text-zinc-500">Dark #09090b zinc-900/950 accent hsl 262 60% 58%</div>
                </div>
                <Badge variant="muted">Dark only MVP</Badge>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <div>
                  <div className="text-xs text-zinc-300">Font</div>
                  <div className="text-[11px] text-zinc-500">Geist/Inter + JetBrains Mono • shadcn/ui</div>
                </div>
                <Badge variant="muted">Geist</Badge>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <div>
                  <div className="text-xs text-zinc-300">Reduced Motion</div>
                  <div className="text-[11px] text-zinc-500">Respects prefers-reduced-motion • Framer Motion 2D • R3F 3D calm</div>
                </div>
                <Badge variant="secondary">Auto</Badge>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
            <h3 className="text-sm font-medium text-zinc-200">Runtime • D7 Docker Compose</h3>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <div className="text-zinc-500">Deployment</div>
                <div className="text-zinc-300 mt-1 font-mono">Docker Compose • MVP</div>
                <div className="text-[11px] text-zinc-600 mt-1">K8s future, no Fly/Hetzner/Vercel commitment</div>
              </div>
              <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <div className="text-zinc-500">3D</div>
                <div className="text-zinc-300 mt-1">Hybrid Orbital + Layered DAG • D5</div>
                <div className="text-[11px] text-zinc-600 mt-1">Runtime focus, not entire memory/vector DB</div>
              </div>
              <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <div className="text-zinc-500">Sandbox</div>
                <div className="text-zinc-300 mt-1">SandboxService abstraction</div>
                <div className="text-[11px] text-zinc-600 mt-1">Container isolation, no unrestricted host</div>
              </div>
              <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <div className="text-zinc-500">Approvals</div>
                <div className="text-zinc-300 mt-1">Balanced • D6</div>
                <div className="text-[11px] text-zinc-600 mt-1">Shell always approval</div>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
            <h3 className="text-sm font-medium text-zinc-200">Security • D4 Single Bearer</h3>
            <div className="space-y-3">
              <div className="space-y-2">
                <label className="text-xs text-zinc-400">Dev Bearer Token • placeholder, no real secret</label>
                <Input value={bearer} onChange={(e) => setBearer(e.target.value)} className="font-mono text-xs" />
                <p className="text-[11px] text-zinc-600">D4 single dev Bearer token for MVP. WS auth via initial message, not ?token= in URL. No API keys in UI.</p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-[11px] text-zinc-500 leading-relaxed">
                Security: no API keys tokens credentials eval exec compile unnecessary network in this frontend. .env not committed. .gitignore covers .env node_modules __pycache__ .pytest_cache .next.
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-2">
            <h3 className="text-sm font-medium text-zinc-200">About • D8 Codename • D9 MIT • D10 Scaffold First</h3>
            <p className="text-xs text-zinc-500 leading-relaxed">
              NEXUS is internal repository/project codename, public name finalized later because multiple existing projects already use NexusOS. MIT license. Scaffold repository first decision.
            </p>
            <div className="flex gap-2 flex-wrap">
              <Badge variant="muted" className="text-[10px]">
                D1 custom ModelProvider
              </Badge>
              <Badge variant="muted" className="text-[10px]">
                D2 local embedding
              </Badge>
              <Badge variant="muted" className="text-[10px]">
                D3 pnpm
              </Badge>
              <Badge variant="muted" className="text-[10px]">
                D4 Bearer token
              </Badge>
              <Badge variant="muted" className="text-[10px]">
                D5 hybrid 3D
              </Badge>
              <Badge variant="muted" className="text-[10px]">
                D6 balanced approval
              </Badge>
              <Badge variant="muted" className="text-[10px]">
                D7 Docker Compose
              </Badge>
              <Badge variant="muted" className="text-[10px]">
                D8 codename
              </Badge>
              <Badge variant="muted" className="text-[10px]">
                D9 MIT
              </Badge>
              <Badge variant="muted" className="text-[10px]">
                D10 scaffold first
              </Badge>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
