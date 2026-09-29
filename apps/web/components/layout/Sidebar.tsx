"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  ListTodo,
  Bot,
  Brain,
  Wrench,
  ShieldCheck,
  BarChart3,
  Settings,
  Command,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  count?: number;
  highlight?: boolean;
  badge?: string;
}

const navItems: NavItem[] = [
  { name: "Mission Control", href: "/", icon: LayoutDashboard },
  { name: "Missions", href: "/missions", icon: ListTodo, count: 6 },
  { name: "Agents", href: "/agents", icon: Bot, count: 4 },
  { name: "Memory", href: "/memory", icon: Brain, count: 128 },
  { name: "Tools / MCP", href: "/tools", icon: Wrench, count: 12, badge: "stdio" },
  { name: "Approvals", href: "/approvals", icon: ShieldCheck, count: 2, highlight: true },
  { name: "Observability", href: "/observability", icon: BarChart3 },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-full lg:w-[260px] shrink-0 border-b lg:border-b-0 lg:border-r border-zinc-800/80 bg-zinc-900/20 backdrop-blur-sm flex flex-col">
      <div className="p-3 lg:p-4 flex-1 space-y-6 overflow-y-auto">
        {/* Navigation */}
        <nav className="space-y-1" aria-label="Main navigation">
          <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-widest px-3 py-2">Platform</div>
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "group flex items-center justify-between px-3 py-2.5 rounded-xl text-sm transition-all duration-200",
                  isActive
                    ? "bg-violet-500/10 text-violet-100 border border-violet-500/20 shadow-soft"
                    : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50 border border-transparent"
                )}
                aria-current={isActive ? "page" : undefined}
              >
                <span className="flex items-center gap-3">
                  <Icon className={cn("w-4 h-4 transition-colors", isActive ? "text-violet-400" : "text-zinc-500 group-hover:text-zinc-400")} />
                  <span className="font-medium tracking-tight">{item.name}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  {item.badge && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-500 border border-zinc-700/50 font-mono">
                      {item.badge}
                    </span>
                  )}
                  {item.count !== undefined && (
                    <span
                      className={cn(
                        "text-[10px] px-2 py-0.5 rounded-full font-medium min-w-[20px] text-center",
                        item.highlight
                          ? "bg-amber-500/15 text-amber-300 border border-amber-500/20"
                          : isActive
                          ? "bg-violet-500/20 text-violet-300"
                          : "bg-zinc-800 text-zinc-500 border border-zinc-700/30"
                      )}
                    >
                      {item.count}
                    </span>
                  )}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* Runtime Status */}
        <div className="space-y-3">
          <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-widest px-3">Runtime</div>
          <div className="px-3 space-y-2.5">
            {[
              { label: "Active Missions", value: "1 running", dot: "bg-violet-500", mono: false, badge: undefined as string | undefined },
              { label: "Agents", value: "4 • 2 active", dot: "bg-emerald-500", mono: false, badge: undefined as string | undefined },
              { label: "Model Provider", value: "OpenAI-compat", dot: undefined as string | undefined, mono: true, badge: undefined as string | undefined },
              { label: "Embedding", value: "local-first", dot: undefined as string | undefined, mono: true, badge: undefined as string | undefined },
              { label: "MCP Transport", value: "stdio + http", dot: undefined as string | undefined, mono: true, badge: "D6" },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between text-xs">
                <span className="text-zinc-500 flex items-center gap-2">
                  {item.dot && <span className={`w-1.5 h-1.5 rounded-full ${item.dot} animate-pulse`} />}
                  {item.label}
                </span>
                <span className={cn("text-zinc-300", item.mono ? "font-mono text-[11px] text-zinc-400" : "")}>
                  {item.value}
                  {item.badge && <span className="ml-1.5 text-[9px] px-1 py-0.5 rounded bg-zinc-800 text-zinc-500">{item.badge}</span>}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Scaffold Status Card */}
        <div className="p-3.5 rounded-xl bg-zinc-900/80 border border-zinc-800 shadow-soft space-y-2.5">
          <div className="flex items-center gap-2">
            <Command className="w-3.5 h-3.5 text-violet-400" />
            <span className="text-xs font-medium text-zinc-200">Phase 2A Prototype</span>
            <Badge variant="secondary" className="text-[9px] ml-auto">
              Mock
            </Badge>
          </div>
          <p className="text-[11px] text-zinc-500 leading-relaxed">
            Polished Mission Control UI + 3D runtime prototype. Mock runtime data only. Real orchestration, MCP execution, RAG, and LLM calls are future phases.
          </p>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {["D1 ModelProvider", "D2 Local Embed", "D5 Hybrid 3D", "D6 Approval"].map((tag) => (
              <span key={tag} className="text-[9px] px-2 py-1 rounded-full bg-zinc-800/80 text-zinc-500 border border-zinc-700/30">
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Decisions */}
        <div className="px-3 pb-2">
          <div className="text-[10px] text-zinc-600 leading-relaxed">
            D1 custom ModelProvider, D2 local embedding, D3 pnpm, D4 Bearer token, D5 hybrid 3D, D6 balanced approval shell always, D7 Docker Compose, D8 codename, D9 MIT, D10 scaffold first
          </div>
        </div>
      </div>

      {/* Bottom */}
      <div className="p-3 border-t border-zinc-800/80">
        <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-900 border border-zinc-700 flex items-center justify-center">
            <span className="text-[10px] font-mono text-zinc-400">v0.2</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-zinc-300 font-medium">Scaffold → UI</div>
            <div className="text-[10px] text-zinc-500">Phase 2A • Frontend only</div>
          </div>
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        </div>
      </div>
    </aside>
  );
}
