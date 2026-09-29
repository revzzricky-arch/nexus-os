# NEXUS (Codename) - 3D Design Document - Runtime Visualization

**Status:** Scaffold v0.2 Approved
**Date:** 2026-09-29
**Decisions:** D5 Hybrid orbital agents + layered task DAG, runtime focus only

> NEXUS is temporary codename, public name TBD. 3D is core product feature visualizing real runtime state, not decorative.

## Approved Runtime Visualization Model

### Focus (Per Review)
3D scene focuses on **mission runtime state only**:
- agents
- active tasks
- workflows
- tool activity
- approval gates
- event particles (handoff, tool calls)

**Explicitly NOT rendered as raw 3D nodes:**
- Entire memory/vector database
- RAG chunks as individual orbs
- Long-term memory entries as cloud
- Full knowledge base

Memory/RAG activity visualized abstractly (pulse on Mission Core, brief beam, indicator), details in 2D side panel with citations.

### Layout: Hybrid Orbital + Layered DAG (D5)

**Concept: Orbital Command Deck**

- **Center: Mission Core**
  - Sphere 1.5 radius, MeshPhysicalMaterial transmission 0.2, clearcoat 1, emissive based on status
  - Status: running=violet, completed=emerald, failed=red, awaiting_approval=amber
  - Inner core: icosahedron with shader noise, slight rotation
  - Status ring: torus 1.8 radius, emissive
  - Abstract memory activity: subtle ring pulse when RAG/memory accessed, not raw DB nodes
  - Slight rotation, inner glow based on mission health

- **Inner Orbit (Radius 3): Active Agents**
  - 3-8 orbs/pillars orbiting slowly around core
  - Geometry: icosahedron (or researcher=octahedron, coder=box, analyst=dodecahedron) but consistent for MVP: icosahedron with color accent
  - Size: workload, height: importance
  - Orbit speed: activity (faster when running/tool_calling)
  - Position: angle = (index/total)*2π + time*orbitSpeed, y = 0.5 + sin(time)*0.2 float
  - States visual: idle=#52525b, queued=#71717a, planning=#a78bfa pulse 1.5s, running=#8b5cf6 pulse 0.8s emissive 0.8 orbit 0.8, tool_calling=#22d3ee fast pulse 0.4s emissive 1.0, waiting_approval=#fbbf24 amber pulse 2s ring torus, waiting_dependency=#60a5fa dashed ring, completed=#34d399 steady glow 0.5, failed=#f87171 flicker burst, cancelled dim

- **Middle Orbit (Radius 6): Task Nodes - Layered DAG**
  - Smaller nodes (box 0.5x0.15x0.5) representing active tasks
  - Layout: layered by DAG depth (topological sort, layer = max dependency depth, angle = indexInLayer/count*2π, radius = 6+layer*1.5, y=0)
  - Completed tasks settle to y=-0.5 plane
  - Color: pending #27272a, running #8b5cf6, completed #10b981, failed #ef4444

- **Edges: Workflow Splines**
  - CatmullRomCurve3 with 20 points, tube radius 0.02, 64 segments
  - Color based on status, particle flow via shader time uniform
  - Arrow head cone at target
  - Highlight on hover/select: emissive 2x, others dim

- **Tool Activity (Runtime Only)**
  - Particle emitted from agent, color by risk: low=cyan, medium=amber, high=red
  - Moves to tool orb (small cube 0.15 near agent) or to Mission Core abstractly
  - Success: reaches target burst, Failure: turns red falls
  - Points with shader material, 500 max, upward drift

- **Approval Gates (Runtime)**
  - Hexagonal torus radius 0.5 tube 0.05 6 sides, rotation x=90deg on spline
  - Amber #fbbf24 when pending, slow rotation z, pulse scale 1.0-1.1
  - Blocks particle flow when pending, opens (scale y to 0) green flash on approve, red burst on deny

- **Event Particles**
  - Handoff: particle along spline from source agent to target, color #a78bfa trail via Points
  - Message: smaller faster
  - Error: red burst 10 particles explode gravity fall
  - Completion: green ring expands fades

- **Ground**
  - Plane 100x100 #0f0f10, Grid helper divisions 50 opacity 0.1, FogExp2 #0a0a0b density 0.02, subtle not dominant

### Camera Behavior

- Type: Perspective fov 50 near 0.1 far 1000
- Controls: OrbitControls dampingFactor 0.05 rotate 0.5 zoom 1.0 pan 0.5
- Limits: minDistance 5 maxDistance 30 maxPolarAngle PI/2.1 minPolarAngle 0.1
- Focus: On select, lerp camera position offset from target (3 units away 2 up) lerp target to agent, duration 800ms cubicOut
- Reset: Double-click empty or button resets to [0,8,15] target [0,0,0]
- Auto-orbit optional toggle 0.05 rad/s when idle pauses on interaction
- Shake on failure 0.1 intensity 200ms

### Lighting

- Ambient 0.4
- Directional [5,10,5] intensity 0.8
- Point at core intensity 0.5 color violet
- No harsh neon, no point lights per agent for perf
- Environment HDRI city preset soft

### 3D State Model (Runtime Only)

```typescript
type Agent3DState = {
  id: string
  position: [x,y,z] // orbit calc
  scale: number
  color: string
  emissiveIntensity: number
  orbitSpeed: number
  status: AgentState
  toolCallCount: number
  hasApproval: boolean
  isSelected: boolean
}

type Task3DState = {
  id: string
  position: [x,y,z] // layered DAG
  status: TaskStatus
  layer: number
  dependencyEdges: string[]
  progress: number
}

type Event3D = {
  id: string
  type: 'handoff'|'tool_call'
  from: [x,y,z]
  to: [x,y,z]
  color: string
  duration: number
}

type ApprovalGate3D = {
  id: string
  position: [x,y,z] // on edge
  status: ApprovalStatus
  rotation: number
}
```

**State Derivation:**
- Frontend Zustand useMission3DStore subscribes to WS events (future), updates immutably
- Positions calculated via layout algorithms: agents orbital, tasks layered DAG
- Reactivity: agent_state_changed -> lerp color/emissive/orbitSpeed, tool_call -> spawn particle, approval -> spawn gate
- Throttled to 60fps via useFrame, WS batched max 10 per frame

### 2D/3D Interaction

- **Hover:** Raycaster, scale 1.1 emissive 1.2 tooltip via Html with name/status/tokens, cursor pointer
- **Click:** Agent -> select, Zustand selectedId, side panel, camera focus lerp. Task -> select task, highlight dependencies. Gate -> approval modal. Empty -> deselect. Core -> mission overview
- **Selection:** Selected emissive 2x outline via wireframe, scale 1.2, others dim opacity 0.6, side panel synced tabs Overview/Timeline/Tool Calls/Memory/Cost
- **Filtering:** Top bar search/type/status, dims non-matching opacity 0.2 scale 0.8
- **Zoom/Pan:** OrbitControls damping, wheel/pinch, right-click pan, double-click focus/reset, F focus selected Esc deselect 0 reset

### Responsive / Mobile Fallback

- Desktop 1280px+: full 3D + panels 60fps
- Tablet 768-1279: 3D full width, bottom sheet 50% draggable, reduced particles 50%, simplified materials
- Mobile <768: fallback to 2D list view, message "3D best on desktop", vertical timeline agent cards DAG list, option "Try 3D anyway" warning, touch controls if enabled, auto fallback if FPS <20 for 3s
- WebGL check WEBGL.isWebGL2Available, context lost handling

### Performance Strategy (Scaffold)

- InstancedMesh for agents max 50, tasks max 100
- Points for particles max 500
- useMemo geometries/materials, no recreation per frame
- Frustum culling on, LOD distance>15 simpler, texture max 1k compressed, no shadows MVP, no bloom or subtle
- Debounce resize, throttle WS batch, code split 3D canvas dynamic ssr false
- DPR capped 2, throttle raycast 30fps, batch WS, dispose on unmount, measure FPS auto reduce quality if <30fps

### Relationship Between Backend Runtime State and Future 3D State

**Backend -> Event Bus -> Frontend 3D:**

1. Backend AgentRunner emits event (agent_state_changed, tool_call_started, approval_requested, etc.) -> writes to Redis Stream (XADD) + PubSub (PUBLISH) [Future, scaffold contract only]
2. FastAPI WS gateway subscribes to PubSub for missions user owns, forwards to WS clients [Future]
3. Frontend WS client receives, validates Zod, updates TanStack Query cache + Zustand 3D store
4. Zustand store batches, triggers re-render via useFrame lerp
5. 3D components read Zustand state, animate

**Current Scaffold:**
- No real Redis/WS streaming yet
- Mock runtime state: 3 placeholder agents (researcher running, coder tool_calling with approval, analyst queued), 3 tasks layered DAG, workflow splines, approval gate pending, event particles
- Demonstrates hybrid orbital+layered DAG, runtime focus, no vector DB nodes

**Future Real Implementation:**
- Agent positions derived from orbit index + activity from backend agent state
- Task positions derived from DAG layer from backend task dependencies
- Tool activity particles spawned on tool_call_started event
- Approval gates spawned on approval_requested event, opened on approval_decided
- Handoff particles on handoff event
- Memory activity abstract pulse on core on memory_accessed/rag_queried event, not raw nodes

### WebGL Considerations

- Check isWebGL2Available, fallback to 2D
- Handle context lost: preventDefault, show fallback
- Max textures <8 compressed, powerPreference high-performance, antialias true but disable if low-end hardwareConcurrency
- Memory dispose geometries/materials limit 100MB

### No Advanced Shaders in Scaffold

- No custom shader effects for states (use standard material emissiveIntensity)
- No postprocessing bloom heavy (optional subtle later)
- No memory galaxy visualization
- Keep materials simple: MeshStandardMaterial low metalness roughness

---

**Scaffold Prototype Implements:**
- Mission Core central orb with status + abstract memory pulse
- 3 agent nodes orbital with state colors (running violet, tool_calling cyan with amber approval ring, queued zinc)
- 3 task nodes layered DAG
- Workflow splines with status colors and arrow heads
- Approval gate hex torus amber pending
- Event particles tool activity runtime only
- OrbitControls, PerspectiveCamera, Grid, Environment, Fog
- Responsive, dark professional, desaturated violet accent, glass/translucent, subtle lighting, technical typography, no neon, no gaming aesthetic

**Not Implemented (Per Scaffold Limits):**
- Full vector DB as raw nodes
- Advanced shaders, bloom, LOD, minimap
- Real backend event streaming (contract only)
- Real tool execution, MCP, RAG, LLM calls
