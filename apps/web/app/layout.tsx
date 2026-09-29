import type { Metadata } from "next";
import "./globals.css";
import { RuntimeProvider } from "@/lib/runtime/providers";

export const metadata: Metadata = {
  title: "NEXUS (Codename) - Mission Control",
  description:
    "3D Agent Operating System / AI Agent Command Center - Scaffold Phase. Temporary codename NEXUS, public name TBD.",
  keywords: ["agent-os", "ai-agents", "mission-control", "3d", "orchestration"],
  authors: [{ name: "NEXUS Team (Codename)" }],
  openGraph: {
    title: "NEXUS (Codename) - Mission Control",
    description: "3D Agent Operating System - Scaffold Phase",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <style>{`
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
          :root {
            --font-geist-sans: 'Inter', system-ui, sans-serif;
            --font-geist-mono: 'JetBrains Mono', monospace;
          }
        `}</style>
      </head>
      <body className="min-h-screen bg-[#09090b] text-zinc-100 antialiased selection:bg-violet-500/30">
        {/* Background subtle grid + radial */}
        <div className="fixed inset-0 -z-10">
          <div className="absolute inset-0 bg-[#09090b]" />
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#27272a_1px,transparent_1px),linear-gradient(to_bottom,#27272a_1px,transparent_1px)] bg-[size:4rem_4rem] opacity-[0.03]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_hsl(262_60%_58%_/_0.08),transparent_60%)]" />
        </div>
        <RuntimeProvider defaultMode="mock">{children}</RuntimeProvider>
      </body>
    </html>
  );
}
