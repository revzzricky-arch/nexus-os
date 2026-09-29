# ADR 004: 3D Library and Scene Design

**Status:** Accepted (v0.2 Review - Runtime Focus)
**Date:** 2026-09-29
**Decisions:** D5 Hybrid orbital + layered DAG, runtime focus

## Context
3D is core feature, must visualize real runtime state, not decorative. Review requires hybrid orbital + layered DAG and focus on runtime state only, not raw vector DB.

## Decision
- **Library:** Three.js (current stable) + React Three Fiber 9 + Drei (current stable) + Zustand 3D store + Framer Motion 3D
- **Layout:** Hybrid orbital agents + layered task DAG (D5)
  - Inner orbit radius 3: Active agents (3-8 orbs, icosahedron, state colors, orbit speed = activity)
  - Middle orbit radius 6: Task nodes layered by DAG depth, splines for dependencies
  - Center: Mission Core orb with status ring
  - Edges: Workflow splines with particle flow
  - Tool activity: particles/beams from agents
  - Approval gates: hex torus on edges, amber pulse
- **Focus:** Mission runtime state only: agents, active tasks, workflows, tool activity, approval gates
- **Explicitly NOT:** Entire memory/vector DB as raw 3D nodes (50-100 orbs). Memory/RAG activity abstracted as pulse on core or brief beam, 2D panel shows details.
- **Performance:** InstancedMesh for agents/tasks, Points for particles, useMemo geometries, no shadows MVP, frustum culling, LOD, DPR capped 2, adaptive quality fallback to 2D on mobile
- **Interaction:** Raycast hover, click select -> Zustand + side panel + camera lerp focus, filtering dims non-matching, OrbitControls with damping
- **Stack:** Next.js 16.x + React 19, no hard-pinned patch versions

## Consequences
- Legible runtime topology
- 60fps target with 20 agents
- No clutter from full DB rendering
- Mobile fallback to 2D

## Alternatives Rejected
- Full memory cluster as 50-100 orbs: expensive, cluttered, rejected per review
- Pure orbital or pure DAG: less legible than hybrid
- Raw Three.js without R3F: more boilerplate
- Hard-pinned R3F 8: outdated, review requires R3F 9
