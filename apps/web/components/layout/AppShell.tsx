"use client";

import { TopBar } from "./TopBar";
import { Sidebar } from "./Sidebar";
import { useRuntimeStore } from "@/lib/store/runtime";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const activeMission = useRuntimeStore((s) => s.activeMission);

  return (
    <div className="min-h-screen flex flex-col bg-[#09090b]">
      {/* Background layers */}
      <div className="fixed inset-0 -z-10 pointer-events-none">
        <div className="absolute inset-0 bg-[#09090b]" />
        <div className="absolute inset-0 bg-grid opacity-[0.02] bg-grid-fade" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_hsl(262_60%_58%_/_0.06),transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,_hsl(262_60%_58%_/_0.04),transparent_50%)]" />
      </div>

      <TopBar
        activeMission={
          activeMission ? { title: activeMission.title, status: activeMission.status } : null
        }
        systemStatus="operational"
      />

      <div className="flex-1 flex flex-col lg:flex-row min-h-0">
        <Sidebar />
        <main className="flex-1 min-w-0 bg-zinc-950/20">{children}</main>
      </div>
    </div>
  );
}
