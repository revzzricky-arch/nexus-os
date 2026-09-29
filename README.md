# NEXUS (Codename) - 3D Agent Operating System / AI Agent Command Center

> **IMPORTANT:** NEXUS / NexusOS is currently an **internal repository/project codename only**. It is NOT claimed as a final unique public brand. Multiple existing projects already use NexusOS. The public product name will be finalized later. See `docs/architecture.md` v0.2 and `docs/adr/011-naming.md`.

## Project Vision

NEXUS is an independently designed **3D Agent Operating System / AI Agent Command Center** — an operating layer for autonomous agents, not a chatbot wrapper.

**Core Thesis:** As agent teams become longer-running, multi-step, and tool-heavy, humans need a mission-control interface that makes agent state, intent, and action *legible* and *intervenable* in real time. 3D is not decoration — it is a spatial map of runtime topology.

**Key Features (Planned):**
- Multi-agent orchestration with supervisor agent
- Specialized agents (Researcher, Coder, Analyst)
- Persistent shared memory + RAG (local-first embedding)
- MCP integration (stdio local + Streamable HTTP remote)
- Tool registry + permission model (balanced, shell always approval)
- Human approval gates (visible in 3D)
- Workflow/missions DAG
- Real-time agent events + audit logs
- Observability (OTel, Prometheus, cost tracking)
- Model-provider abstraction (OpenAI-compatible incl Arena, Anthropic, Ollama)
- Beautiful futuristic web interface + interactive 3D mission-control (core feature)

**3D Focus (Approved):** Mission runtime state only — agents, active tasks, workflows, tool activity, approval gates. Hybrid orbital agents + layered task DAG. No raw vector DB rendering.

## Current Status: Scaffold Phase (v0.1.0-scaffold)

This phase is **scaffold and 3D prototype only**. No real business logic yet.

**Implemented in Scaffold:**
- Monorepo skeleton (pnpm workspaces)
- Frontend shell: Next.js 16.x + React 19 + TypeScript + Tailwind + shadcn/ui-compatible + Zustand + TanStack Query + Three.js + React Three Fiber 9 + Drei + Framer Motion
  - Dark professional theme, desaturated violet accent, glass/translucent, subtle lighting, technical typography, no neon/gaming
  - Responsive layout, navigation/sidebar, top status bar, dashboard shell, placeholder mission area, activity panel
  - Minimal working 3D runtime prototype: Mission Core central orb, 3 placeholder agent nodes orbital, task nodes layered DAG, workflow splines, approval gate, event particles, camera controls
- Backend shell: FastAPI with health/version endpoints, placeholder service interfaces (supervisor, agent runner, tool registry, permission, MCP manager stdio+Streamable HTTP, memory, RAG, approval, event bus, evaluation, SandboxService, ModelProvider OpenAI-compat/Anthropic/Ollama, EmbeddingProvider local-first)
- Shared package: Strict TS types for Mission, Agent, Task, Tool, Approval, AgentState, MissionState, EventEnvelope + realtime event contract (no Redis/WS streaming yet)
- Infra: Docker Compose with web, api, postgres+pgvector, redis, sandbox-runner placeholder (no exec), otel-collector placeholder
- Scripts, CI workflow (typecheck/build checks), .gitignore, .env.example
- Docs: architecture.md v0.2 approved, 3d-design.md runtime model, ADR 001-012 with decisions D1-D10 recorded

**NOT Implemented Yet (Honest Limitations):**
- Real agent orchestration, supervisor decomposition, LangGraph DAG execution
- Real MCP integrations (no connections to real servers)
- Real RAG ingestion, chunking, embedding pipeline
- Real model provider API calls (no LLM calls, no API keys)
- Real approvals, tool execution, SandboxService container isolation
- Real memory, vector search, hybrid search
- Real Redis event bus, WebSocket streaming (contract only)
- Auth UI, user accounts, multi-tenancy, RBAC, Kubernetes, cloud deployment, voice, custom agent builder, workflow editor, knowledge graph, advanced shaders, browser automation, unrestricted shell exec

See `docs/architecture.md` for full architecture and `docs/3d-design.md` for 3D runtime model.

## Technology Stack (Scaffold, Updated per Review)

**Frontend (Target Current Stable-Compatible, No Hard-Pinned Patches):**
- Next.js 16.x (App Router)
- React 19
- TypeScript
- Tailwind CSS
- shadcn/ui-compatible (Button, Card, etc.)
- Zustand (client state)
- TanStack Query v5 (server state)
- Three.js (current stable)
- React Three Fiber 9
- Drei (current stable)
- Framer Motion
- lucide-react icons

**Backend:**
- Python 3.12
- FastAPI
- Pydantic v2 + Pydantic Settings
- Uvicorn
- Placeholder interfaces for LangGraph, MCP SDK, pgvector, Redis, etc. (not installed in scaffold to keep minimal)

**Infrastructure:**
- Docker + Docker Compose (MVP deployment target, D7) — no cloud vendor commitment yet
- PostgreSQL + pgvector (image pgvector/pgvector:pg16)
- Redis 7
- Kubernetes as future option, not MVP

**Tooling:**
- pnpm 9.x (D3)
- ESLint, Prettier, TypeScript strict
- Pytest for backend smoke tests
- GitHub Actions CI

**Decisions Recorded (D1-D10):**
- D1: Custom lightweight ModelProvider (OpenAI-compatible incl Arena, Anthropic, Ollama)
- D2: Local embedding first, replaceable
- D3: pnpm
- D4: Single dev Bearer token
- D5: Hybrid orbital agents + layered task DAG
- D6: Balanced approval, shell always approval
- D7: Docker Compose first
- D8: NEXUS temporary codename
- D9: MIT
- D10: Scaffold first

## Repository Structure (Scaffold)

```
nexus-os/ (codename, public name TBD)
├── README.md (this file)
├── .gitignore
├── .env.example
├── package.json (pnpm workspace root)
├── pnpm-workspace.yaml
├── docs/
│   ├── architecture.md (v0.2 approved)
│   ├── 3d-design.md (runtime visualization model)
│   └── adr/ (001-012 decisions)
├── apps/
│   ├── web/ (Next.js 16.x + React 19 + R3F 9 + 3D prototype)
│   │   ├── app/ (layout, page, globals.css)
│   │   ├── components/ui/ (Button, Card) + 3d/Scene,MissionCore,AgentNode,TaskNode,WorkflowSplines,ApprovalGate,EventParticles + mission/
│   │   ├── lib/api,ws,store,3d,utils
│   │   ├── hooks/
│   │   ├── public/
│   │   ├── next.config.js, tailwind.config.js, tsconfig.json
│   │   ├── Dockerfile
│   │   └── package.json
│   └── api/ (FastAPI scaffold)
│       ├── app/
│       │   ├── main.py (health, version, root)
│       │   ├── config.py (Pydantic Settings)
│       │   ├── routers/ (health, missions, tasks, agents, tools, mcp, memory, rag, approvals, ws)
│       │   ├── services/ (supervisor, agent_runner, tool_registry, permission, mcp_manager, memory, rag, approval, event_bus, evaluation)
│       │   ├── agents/base.py, tools/builtin, core/model_provider,embedding_provider,sandbox,security, db/base.py
│       │   └── __init__.py
│       ├── tests/test_health.py (smoke tests)
│       ├── requirements.txt, pyproject.toml, Dockerfile
├── packages/
│   └── shared/ (TS types: Mission, Agent, Task, Tool, Approval, AgentState, MissionState, EventEnvelope, common)
├── infra/
│   ├── docker-compose.yml (web, api, postgres+pgvector, redis, sandbox-runner placeholder, otel-collector)
│   ├── otel-collector.yaml
│   └── init-db/01-init.sql
├── scripts/
│   ├── dev.sh
│   └── gen-openapi.sh
├── .github/
│   └── workflows/
│       └── ci.yml (frontend typecheck/build, backend compile/test)
```

## Local Development

### Prerequisites

- Node.js >=20
- pnpm >=9 (`corepack enable && corepack prepare pnpm@9.12.3 --activate`)
- Python 3.12
- Docker + Docker Compose (for postgres, redis)

### Install Dependencies

**Frontend + Shared:**
```bash
# From repo root
cp .env.example .env
# Edit .env if needed (no real keys needed for scaffold)

pnpm install
```

**Backend:**
```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Start Frontend (Next.js 16.x)

```bash
# From root
pnpm dev:web
# or
cd apps/web
pnpm dev
# Runs on http://localhost:3000
```

**Verification:**
- Dashboard loads with dark futuristic theme
- Sidebar navigation visible
- Top status bar shows NEXUS codename + scaffold status
- 3D runtime prototype mounts: Mission Core central, 3 agent nodes orbital, task nodes layered, workflow splines, approval gate, event particles
- Click agent node to select, side panel updates
- Toggle 3D on/off
- No excessive neon, no gaming aesthetic

### Start Backend (FastAPI)

```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# or from root: pnpm dev:api (if configured)
```

**Verification:**
```bash
curl http://localhost:8000/health
# {"status":"ok","service":"nexus-api","env":"development","version":"0.1.0-scaffold","codename":"NEXUS",...}

curl http://localhost:8000/version
# {"service":"nexus-api","version":"0.1.0-scaffold","codename":"NEXUS","stack":{...},"decisions":{...}}

curl http://localhost:8000/
# root with codename note and limitations

# Docs
open http://localhost:8000/docs
```

### Docker Compose Usage (MVP Deployment Target)

**MVP deployment target is Docker Compose only, no cloud vendor commitment (D7).**

```bash
# From repo root
cp .env.example .env

# Start postgres + redis only (for local dev without Docker web/api)
docker compose -f infra/docker-compose.yml up -d postgres redis

# Or start all services (web, api, postgres, redis)
docker compose -f infra/docker-compose.yml up -d

# Logs
docker compose -f infra/docker-compose.yml logs -f

# Down
docker compose -f infra/docker-compose.yml down

# Parse check (no start)
docker compose -f infra/docker-compose.yml config

# Optional profiles
docker compose -f infra/docker-compose.yml --profile sandbox up -d  # sandbox-runner placeholder, no exec
docker compose -f infra/docker-compose.yml --profile observability up -d  # otel-collector placeholder
```

**Services:**
- postgres: pgvector/pgvector:pg16, port 5432, volume postgres_data, healthcheck
- redis: redis:7-alpine, port 6379, AOF, volume redis_data
- api: FastAPI, port 8000, depends_on postgres+redis healthy, volume for hot reload
- web: Next.js 16.x, port 3000, depends_on api healthy
- sandbox-runner: alpine placeholder, profile sandbox, read-only, no exec yet (per scaffold limits)
- otel-collector: placeholder, profile observability

**Environment:**
- All config via .env, never hardcoded secrets
- No real API keys in repo, only placeholders in .env.example
- Auth: Bearer token via header X-Nexus-Token or Authorization: Bearer, NEVER ?token= in URL (see app/core/security.py and shared/src/events.ts WSAuthMessage)

### Testing

**Backend Smoke Tests:**
```bash
cd apps/api
pytest -v
# Tests /health and /version
```

**Frontend Type/Build Checks:**
```bash
cd apps/web
pnpm typecheck
pnpm build
# Verifies TS, 3D scene mounts without crashing (via build)
```

**Docker Compose Parse:**
```bash
docker compose -f infra/docker-compose.yml config
```

**Security Scan (Manual):**
```bash
# Search for hardcoded secrets, eval, exec, compile
grep -r "sk-" --include="*.ts" --include="*.tsx" --include="*.py" . || echo "No hardcoded OpenAI keys"
grep -r "api_key.*=" --include="*.ts" --include="*.py" apps/ || echo "No hardcoded api_key assignment in source (should be env only)"
grep -rn "eval(" apps/ || echo "No eval("
grep -rn "exec(" apps/ --include="*.py" | grep -v "exec_command" | grep -v "placeholder" || echo "No unexpected exec("
```

## Architecture

See `docs/architecture.md` v0.2 for full architecture (40 sections + 3D deep dive + data flows + security + diagrams + final decisions).

Key points:
- Layered event-driven zero-trust agent OS
- LangGraph for durable DAG + checkpoint + human-in-loop
- Postgres+pgvector for memory/RAG, Redis Streams+PubSub for events (contract only in scaffold)
- SandboxService abstraction, container isolation for exec, no unrestricted host access
- MCP stdio local + Streamable HTTP remote, SSE legacy only
- ModelProvider lightweight (OpenAI-compatible incl Arena, Anthropic, Ollama), EmbeddingProvider local-first replaceable
- 3D hybrid orbital+layered DAG, runtime focus only

## 3D Design

See `docs/3d-design.md` for approved runtime visualization model:
- Mission Core central orb with status + abstract memory pulse (not raw DB)
- Agent orbit inner radius 3, 3 placeholder agents with state colors
- Task DAG middle radius 6 layered by dependency depth
- Workflow splines curved with particles
- Tool activity particles/beams runtime only
- Approval gates hex torus amber pending
- Event particles handoff/tool calls
- Camera OrbitControls, responsive, mobile fallback 2D

Relationship backend runtime -> 3D: Backend emits event -> Redis Stream+PubSub (future) -> WS gateway -> frontend Zustand store -> useFrame lerp -> 3D render. Scaffold has mock runtime state only.

## CI

Minimal GitHub Actions workflow `.github/workflows/ci.yml` verifies:
- Frontend: pnpm install, typecheck, build
- Backend: pip install, compile/import checks, pytest smoke tests /health /version
- Docker Compose config parse
- No complicated pipeline in scaffold

## Known Limitations (Scaffold Phase - Honest)

- No real agent orchestration, no supervisor decomposition, no LangGraph execution
- No real MCP server connections (interface only, transport terminology per review)
- No real RAG ingestion, chunking, embedding pipeline (local-first stub only)
- No real model provider API calls (ModelProvider stubs, no keys, no LLM calls)
- No real approvals, no tool execution, no SandboxService container isolation (placeholder, no exec)
- No real memory, no vector search, no hybrid search
- No real Redis event bus, no WebSocket streaming (event envelope contract only, WS auth via initial message not ?token= in URL)
- No auth UI, no user accounts, no multi-tenancy, no RBAC, no Kubernetes, no cloud deployment, no voice, no custom agent builder, no workflow editor, no knowledge graph, no advanced shaders, no browser automation
- Frontend is polished shell + 3D prototype only, not full UI
- Backend is health/version + placeholder routers/services only
- Database: postgres+pgvector infra only, no full schema yet
- 3D: 3 placeholder agents, 3 task nodes, simple workflow, not hundreds of objects, not full vector DB

## Security Notes (Scaffold)

- **Auth:** Development Bearer token via header `Authorization: Bearer <token>` or `X-Nexus-Token`, NEVER `?token=SECRET` in URL (per review). For WS, initial auth message after connection: `{type: "auth", token: "..."}`, not query param. See `apps/api/app/core/security.py` and `packages/shared/src/events.ts` WSAuthMessage.
- **Sandbox:** Placeholder SandboxService, no host shell execution, no unrestricted filesystem access, agents never receive host access. Container isolation planned for Phase 2.
- **Secrets:** No hardcoded API keys, tokens, passwords in source. All via .env (not committed). .env.example has placeholders only. .gitignore blocks .env, secrets/, *.pem, etc.
- **MCP:** Transport stdio local + Streamable HTTP remote, SSE legacy only, no real connections in scaffold.
- **Scanning:** CI should search for hardcoded secrets, eval(, exec(, compile( — scaffold has none except safe placeholder exec_command method name.

## License

MIT (D9) - See LICENSE (to be added). Temporary codename NEXUS, public name TBD.

## Next Phase

After scaffold approval, Phase 2 will implement real backend (FastAPI + Postgres schema + Redis event bus + ModelProvider real calls + SandboxService container isolation + permission engine + approval flow) and frontend integration with real API, per architecture v0.2.

**Do NOT implement business logic in scaffold phase.**

---

**Branch:** feat/scaffold (scaffold only, not merged to main)
**Version:** 0.1.0-scaffold
**Docs:** docs/architecture.md v0.2 approved, docs/3d-design.md runtime model, docs/adr/001-012
