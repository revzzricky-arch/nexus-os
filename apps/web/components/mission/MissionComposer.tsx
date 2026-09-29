"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, Command, ArrowRight, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useRuntimeStore } from "@/lib/store/runtime";
import { MockMission } from "@/lib/mock/data";

const missionTypes: { id: MockMission["type"]; label: string; desc: string; icon: string }[] = [
  { id: "Research", label: "Research", desc: "Deep investigation with sources", icon: "◈" },
  { id: "Code", label: "Code", desc: "Build and fix with sandbox", icon: "⬢" },
  { id: "Analysis", label: "Analysis", desc: "Data synthesis and insights", icon: "⬣" },
  { id: "General", label: "General", desc: "Flexible autonomous workflow", icon: "⬔" },
];

const examples = [
  "Investigate the API incident from the latest deployment.",
  "Research top 5 AI agent frameworks and compare features.",
  "Implement secure authentication with JWT and RBAC.",
  "Analyze Q3 revenue metrics and generate report.",
];

export function MissionComposer() {
  const { composerValue, composerType, setComposerValue, setComposerType, runMission, isComposing, setComposing } =
    useRuntimeStore();
  const [isFocused, setIsFocused] = useState(false);

  const handleRun = () => {
    if (!composerValue.trim()) return;
    runMission(composerValue, composerType);
  };

  if (!isComposing) {
    return (
      <div className="p-4">
        <button
          onClick={() => setComposing(true)}
          className="w-full group flex items-center gap-3 px-4 py-3.5 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-violet-500/30 hover:bg-zinc-900/80 transition-all duration-200 text-left"
        >
          <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center group-hover:bg-violet-500/15 transition-colors">
            <Command className="w-4 h-4 text-violet-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-zinc-300 font-medium">New Mission</div>
            <div className="text-xs text-zinc-500">Describe what you want the agents to accomplish</div>
          </div>
          <ArrowRight className="w-4 h-4 text-zinc-600 group-hover:text-violet-400 group-hover:translate-x-0.5 transition-all" />
        </button>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-4 space-y-4 border-t border-zinc-800/80 bg-zinc-900/30"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-violet-400" />
          <h3 className="text-sm font-medium text-zinc-200">Mission Composer</h3>
          <Badge variant="secondary" className="text-[10px]">
            AI Command
          </Badge>
        </div>
        <button
          onClick={() => setComposing(false)}
          className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          Cancel
        </button>
      </div>

      <div className="space-y-3">
        <div className="relative">
          <Textarea
            value={composerValue}
            onChange={(e) => setComposerValue(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="Investigate the API incident from the latest deployment."
            className="min-h-[90px] pr-4 bg-zinc-950 border-zinc-800 focus:border-violet-500/50 text-sm leading-relaxed"
            autoFocus
          />
          <div className="absolute bottom-3 right-3 flex items-center gap-1.5">
            <span className="text-[10px] text-zinc-600 font-mono">{composerValue.length} chars</span>
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-[11px] text-zinc-500 uppercase tracking-widest font-medium">Mission Type</div>
          <div className="grid grid-cols-2 gap-2">
            {missionTypes.map((type) => (
              <button
                key={type.id}
                onClick={() => setComposerType(type.id)}
                className={`p-3 rounded-xl border text-left transition-all duration-200 ${
                  composerType === type.id
                    ? "bg-violet-500/10 border-violet-500/30 text-violet-100"
                    : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm">{type.icon}</span>
                  <span className="text-xs font-medium">{type.label}</span>
                </div>
                <div className="text-[11px] mt-1 leading-snug opacity-80">{type.desc}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-1.5 text-[11px] text-zinc-500">
            <Lightbulb className="w-3 h-3" />
            <span>Examples</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {examples.map((ex, i) => (
              <button
                key={i}
                onClick={() => setComposerValue(ex)}
                className="text-[11px] px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-colors text-left max-w-full truncate"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>

        <Button
          onClick={handleRun}
          disabled={!composerValue.trim()}
          className="w-full h-11 bg-violet-600 hover:bg-violet-700 text-white font-medium tracking-tight disabled:opacity-50 disabled:cursor-not-allowed shadow-glow-violet"
        >
          <span className="flex items-center gap-2">
            RUN MISSION
            <ArrowRight className="w-4 h-4" />
          </span>
        </Button>

        <p className="text-[10px] text-zinc-600 text-center leading-relaxed">
          Mock runtime only — simulates mission-start transition into 3D visualization. Real orchestration is future phase.
        </p>
      </div>
    </motion.div>
  );
}
