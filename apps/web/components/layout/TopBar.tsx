"use client";

import { motion } from "framer-motion";
import { Bell, Settings, User, Activity, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface TopBarProps {
  activeMission?: { title: string; status: string } | null;
  systemStatus?: "operational" | "degraded" | "offline";
}

export function TopBar({ activeMission, systemStatus = "operational" }: TopBarProps) {
  return (
    <header className="sticky top-0 z-40 backdrop-blur-xl bg-zinc-950/80 border-b border-zinc-800/80">
      <div className="flex items-center justify-between px-4 md:px-6 py-3">
        {/* Left: Wordmark + status */}
        <div className="flex items-center gap-4 md:gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-glow-violet">
              <span className="text-white font-bold text-sm tracking-tight">N</span>
            </div>
            <div className="hidden sm:block">
              <h1 className="font-semibold text-zinc-100 tracking-tight text-sm">NEXUS</h1>
              <p className="text-[10px] text-zinc-500 -mt-1 tracking-widest uppercase">Codename • Public name TBD</p>
            </div>
          </div>

          <div className="h-5 w-px bg-zinc-800 hidden md:block" />

          {/* Live system status */}
          <div className="flex items-center gap-2.5">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${systemStatus === "operational" ? "bg-emerald-500 animate-pulse" : systemStatus === "degraded" ? "bg-amber-500" : "bg-red-500"}`} />
              <span className="text-xs text-zinc-400 hidden md:inline">
                {systemStatus === "operational" ? "Operational" : systemStatus === "degraded" ? "Degraded" : "Offline"}
              </span>
            </div>
            <span className="text-[10px] px-2 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-500 hidden lg:inline-flex">
              Docker Compose MVP • D7
            </span>
          </div>

          {/* Active mission indicator */}
          {activeMission && (
            <>
              <div className="h-5 w-px bg-zinc-800 hidden lg:block" />
              <div className="hidden lg:flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/20">
                <Activity className="w-3 h-3 text-violet-400" />
                <span className="text-xs text-violet-200 max-w-[180px] truncate">{activeMission.title}</span>
                <Badge variant={activeMission.status === "running" ? "default" : "secondary"} className="text-[10px] px-1.5 py-0">
                  {activeMission.status}
                </Badge>
              </div>
            </>
          )}
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-1.5 md:gap-2">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900 border border-zinc-800">
            <Zap className="w-3 h-3 text-zinc-500" />
            <span className="text-[11px] text-zinc-500 font-mono">0.1.0-scaffold</span>
            <span className="text-[10px] text-zinc-600">•</span>
            <span className="text-[11px] text-zinc-400">Phase 2A</span>
          </div>

          <button
            aria-label="Notifications"
            className="relative w-9 h-9 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors focus-visible:ring-2 focus-visible:ring-violet-500/50"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-amber-500 rounded-full border border-zinc-900" />
          </button>

          <button
            aria-label="Settings"
            className="w-9 h-9 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors focus-visible:ring-2 focus-visible:ring-violet-500/50"
          >
            <Settings className="w-4 h-4" />
          </button>

          <div className="h-5 w-px bg-zinc-800 hidden md:block" />

          <button
            aria-label="Profile"
            className="w-9 h-9 rounded-xl bg-gradient-to-br from-zinc-800 to-zinc-900 border border-zinc-700 flex items-center justify-center text-zinc-300 hover:from-zinc-700 hover:to-zinc-800 transition-all"
          >
            <User className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
