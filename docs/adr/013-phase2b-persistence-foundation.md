# ADR 013: Phase 2B Persistence Foundation - Minimal Models

**Status:** Accepted
**Date:** 2026-09-29
**PR:** feat/phase2b-persistence-foundation (PR 2B-1)
**Decisions:** Minimal persistence scope, enum reconciliation, event model fix

## Context
Phase 2B requires real backend-driven agent runtime foundation, but PR 2B-1 must stay genuinely small per approved plan corrections. Need SQLAlchemy 2 async + Alembic foundation with only minimum models needed by next PR: users, missions, tasks, task_dependencies, agents, agent_runs, events. Defer tool_registry, mcp_servers, tool_permissions, tool_calls, approvals, audit_logs to later tool/approval PR.

Need to reconcile MissionStatus/AgentState/TaskState/EventType with shared types to avoid second incompatible vocabulary.

Need to fix event data model: agent_id should FK to agents.id, not agent_runs, with separate nullable agent_run_id for execution-instance attribution.

MCP must have no real process/network execution in PR 2B-1.

## Decision

### Scope - Genuinely Small
Implement only:
- users (minimal for FK, single user MVP D4)
- missions (with dag JSONB, approval_policy JSONB, cost tracking)
- tasks (with agent_type, status, input/output JSONB)
- task_dependencies (separate table for DAG dependencies, not UUID[] array, for FK integrity and extensibility)
- agents (registry: supervisor, researcher, coder, analyst)
- agent_runs (execution instances, LangGraph checkpoint placeholder)
- events (append-only, with fix)

Deferred to later PR (tool/approval PR):
- tool_registry, mcp_servers, tool_permissions, tool_calls, approvals, audit_logs

No real MCP process/network execution in this PR. MCP config/interfaces remain future-facing.

### SQLAlchemy 2 Async Foundation
- `app/db/base.py`: DeclarativeBase with naming convention for Alembic
- `app/db/session.py`: async engine via `create_async_engine(settings.database_url)`, async_sessionmaker, `get_session()` dependency for FastAPI, `init_db()` for dev, `close_db()`
- `app/db/seed.py`: seed agents registry only (supervisor, researcher, coder, analyst) config-driven, idempotent, capability/configuration driven not large personalities

### Alembic Async
- `alembic.ini`: script_location app/db/migrations, sqlalchemy.url from DATABASE_URL env or settings.database_url
- `app/db/migrations/env.py`: async, uses `async_engine_from_config`, imports Base.metadata from `app.models`, overrides url from env/settings
- Migration `001_phase2b_persistence_foundation`: creates extension pgcrypto, creates 7 tables with check constraints matching shared enums, indexes, FKs with CASCADE/SET NULL, JSONB for postgres, UUID with gen_random_uuid()
- For tests: models use generic `Uuid` and `JSON` (SQLAlchemy) for sqlite+aiosqlite compatibility, migration uses postgresql.UUID and JSONB for postgres production

### Enum Reconciliation - No Second Vocabulary
Backend enums MUST match `packages/shared/src` exactly:

**MissionStatus** (shared/mission.ts):
draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived

**AgentState** (shared/agent.ts):
idle, queued, planning, running, tool_calling, waiting_approval, waiting_dependency, completed, failed, cancelled

**TaskStatus** (shared/task.ts):
pending, queued, running, awaiting_approval, completed, failed, cancelled, skipped

**EventType** (shared/events.ts):
agent_state_changed, task_status_changed, tool_call_started, tool_call_completed, tool_call_failed, message_created, approval_requested, approval_decided, mission_status_changed, mission_created, handoff, memory_created, memory_accessed, rag_queried, error, cost_updated

**EventSource**:
agent_runner, supervisor, tool_registry, approval_service, memory_service, system, user

**AgentType**:
supervisor, researcher, coder, analyst, custom

Implemented as:
- Python constants `MISSION_STATUSES`, `TASK_STATUSES`, `AGENT_STATES`, `AGENT_TYPES`, `EVENT_TYPES`, `EVENT_SOURCES` in models
- CheckConstraint in SQLAlchemy models
- Pydantic Enum in schemas with identical values
- Tests in `test_enum_reconciliation.py` that assert backend == shared

**Explicit Lifecycle Mapping Documented:**
```
CREATED -> draft
PLANNING -> decomposing, planned
RUNNING -> running
WAITING -> awaiting_approval, paused
COMPLETED -> completed, archived
FAILED -> failed
CANCELLED -> cancelled
```
This mapping covers all MissionStatus and is tested.

No second incompatible vocabulary created.

### Event Data Model Fix
Per review correction:
- `events.agent_id` FK -> `agents.id` (not agent_runs)
- `events.agent_run_id` nullable FK -> `agent_runs.id` for execution-instance attribution

This allows attribution to both registry (agent type) and execution instance (run) without ambiguity.

Migration and model both implement this fix, tested in `test_persistence_foundation.py` and `test_migration.py`.

### Pydantic Schemas
- `schemas/common.py`: Pagination, ErrorResponse, Timestamps, CostTracking
- `schemas/mission.py`: MissionStatus, MissionTemplate, MissionDAG, ApprovalPolicy, MissionCreate, MissionUpdate, MissionResponse, MissionPlan (typed execution plan for LangGraph future)
- `schemas/task.py`: TaskStatus, AgentType, TaskCreate, TaskResponse, TaskDependency
- `schemas/agent.py`: AgentType, AgentState, AgentCreate, AgentResponse, AgentRunCreate, AgentRunResponse (fix: model_config field conflicts with Pydantic v2 reserved name, use alias `model_configuration` with `Field(alias="model_config")` and `populate_by_name=True`, `protected_namespaces=()`)
- `schemas/event.py`: EventType, EventSource, EventCreate, EventResponse, EventEnvelope (matches shared EventEnvelope)

### Seed/Bootstrap
Only agents registry seeded, idempotent, 4 types with role, system_prompt_template concise (<1000 chars), model_config provider openai-compatible/anthropic/ollama, tools, capability_tags. No tool_registry seeding in this PR.

### Security
- No eval/exec/compile in app code
- No unrestricted host filesystem/shell, no MCP process/network execution in this PR
- Secrets only via environment (DATABASE_URL, etc.), no hardcoded
- Bearer-token architecture preserved (D4)
- Existing Phase 2A frontend/3D unchanged

### Testing
- `test_persistence_foundation.py`: models import, create user->mission->task->task_dependency->agent->agent_run->event flow with sqlite+aiosqlite in-memory, unique constraint
- `test_enum_reconciliation.py`: shared files exist, backend model constants == shared, schema enums == shared, explicit lifecycle mapping covers all MissionStatus
- `test_migration.py`: migration file exists, has upgrade/downgrade, contains 7 minimal tables, has fix agent_id/agent_run_id FKs, deferred tables NOT included (genuinely small), has pgcrypto, alembic.ini and env.py async
- `test_seed.py`: agent seeds defined 4 types, config-driven not large personalities, idempotent, correct types/roles

All tests pass with `pytest`.

### Future Considerations
- Any asyncio.create_task/background execution used later must be documented as MVP-only and isolated behind service boundary for durable worker/queue replacement (not in this PR, but noted for next PRs)
- Embedding dimension configurable via EMBEDDING_DIMENSION env (384 default local-first D2), not hardcoded
- JSONB for postgres, JSON for sqlite tests compatibility

## Consequences
- Minimal persistence foundation unblocks next PR (Mission API)
- No second vocabulary, shared types authoritative
- Event model fix prevents ambiguity between agent registry and execution instance
- No MCP execution in this PR keeps scope small
- Async foundation ready for FastAPI
- Tests ensure migration and enum alignment

## Alternatives Rejected
- UUID[] array for task dependencies: rejected, use separate table for FK integrity
- Second incompatible enum vocabulary: rejected, must match shared
- events.agent_id FK to agent_runs: rejected per review fix, use agents.id + separate agent_run_id
- Including tool_registry etc in PR 2B-1: rejected, keep genuinely small per correction
- Real MCP process execution in PR 2B-1: rejected, future-facing only
- Using model_config field name directly in Pydantic: rejected, conflicts with Pydantic v2 reserved, use alias
