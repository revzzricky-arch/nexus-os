# ADR 014: Phase 2B-2 Mission API + EventBus Foundation

**Status:** Accepted
**Date:** 2026-09-29
**PR:** feat/phase2b-mission-api-eventbus (PR 2B-2)
**Decisions:** MissionService lifecycle validator, EventBus Postgres authority + optional Redis, Mission API endpoints, error model, auth boundary

## Context
Phase 2B-1 implemented persistence foundation with 7 tables (users, missions, tasks, task_dependencies, agents, agent_runs, events) and enum reconciliation. Phase 2B-2 needs Mission API + EventBus foundation to enable HTTP→Bearer→FastAPI Router→MissionService→SQLAlchemy→EventBus→Postgres events→future Redis/WS flow.

Target: production-oriented but without real agent execution (no LangGraph, ToolRegistry, approval engine, real MCP). Must preserve Phase 2A frontend UI/3D unchanged, provide Mock Zustand→future adapter→real API+events→future WS boundary.

Need explicit lifecycle validator with single vocabulary (draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived) and typed domain errors. Need EventEnvelope per shared contract (packages/shared/src/events.ts) with Postgres source of truth, optional Redis abstraction not authoritative, in-process async subscriber for tests/future WS, deterministic ordering, mission scoping mandatory, last_event_id replay safe.

Need Bearer Auth D4 reuse (Authorization: Bearer <NEXUS_DEV_TOKEN>, no credentials in URLs), error model {error:{code,message,details}} with mission_not_found/invalid_transition/validation_error/unauthorized/event_not_found/task_not_found, no stack/secrets leak.

Need FastAPI structure app/routers/missions/tasks/events, services/mission/event_bus, schemas existing+additions, dependencies.py database/authentication, no DB logic in routers, service independently testable.

Need focused tests: test_missions_api (auth/create/list/get/missing/validation/transitions/invalid/cancel/pagination), test_event_envelope (schema matches shared/persistence/mission_created/mission_status_changed/deterministic/mission scoping/last_event_id), test_mission_service (lifecycle matrix/domain errors/event emission), test_event_bus (emit persists/list/subscriber/Redis unavailable does not prevent DB persistence/deterministic).

## Decision

### MissionService Boundary
- Responsibilities: create/list/retrieve/update state/cancel/pause/resume/validate lifecycle transitions, no HTTP logic, async SQLAlchemy
- Location: `app/services/mission.py`
- Methods:
  - `create_mission(session, mission_create, user_id)` validates title/goal/template, default draft, emits mission_created via EventBus
  - `list_missions(session, status, template, limit, offset)` pagination, optional status filter, deterministic ordering created_at DESC + id DESC, total+page
  - `get_mission(session, mission_id)` 404 typed MissionNotFoundError
  - `update_mission(session, mission_id, mission_update)` allow explicitly supported fields (status, title), validate transition via explicit validator, emit mission_status_changed when status changes
  - `cancel_mission(session, mission_id)` idempotent if already cancelled, otherwise validate transition to cancelled, persist, emit mission_status_changed

### Lifecycle Vocabulary Reconciled
Single vocabulary, no second vocabulary: draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived (from shared/src/mission.ts, Phase 2B-1).

Explicit transition validator `ALLOWED_TRANSITIONS`:
- draft → decomposing, cancelled, archived
- decomposing → planned, failed, cancelled
- planned → running, failed, cancelled, archived
- running → paused, awaiting_approval, completed, failed, cancelled
- awaiting_approval → running, paused, failed, cancelled, completed
- paused → running, cancelled, failed, archived
- completed → archived
- failed → archived, cancelled
- cancelled → archived
- archived → (terminal, no outgoing)

Examples from spec validated:
draft→decomposing, decomposing→planned, planned→running, running→paused/awaiting_approval/completed/failed/cancelled, paused→running/cancelled.

Reject invalid with typed domain error `InvalidTransitionError` (code invalid_transition, 400). Terminal states no transition back unless architecture explicitly supports (our matrix enforces).

### EventBus Authority
- Location: `app/services/event_bus.py`
- Source of truth: Postgres events table (append-only)
- Optional realtime: Redis behind clean abstraction, NOT authoritative. If Redis unavailable, DB persistence continues, do not lose events. Implementation: `_publish_redis` lazily imports redis.asyncio, swallows ImportError and connection errors, DB already flushed before Redis attempt. Redis publish uses pubsub channel `mission:{mission_id}:events:pubsub` and stream `mission:{mission_id}:events:stream` with maxlen 10000, both optional.
- In-process subscriber: `_subscribers` dict mission→list[Queue], `_publish_in_process` put_nowait to queues, `subscribe(mission_id)` async generator yields events for tests/future WS. Note: This asyncio in-process mechanism is MVP-only and isolated behind service boundary so it can be replaced by durable worker/queue later.
- Methods:
  - `emit(session, event_create)` creates Event with id, type, source, mission_id, task_id nullable, agent_id nullable, agent_run_id nullable, timestamp now UTC, version, payload, metadata_, flushes, refreshes, attempts Redis (isolated), publishes in-process, returns Event.
  - `list(session, mission_id, event_type, from_timestamp, to_timestamp, last_event_id, limit, offset)` mandatory mission scoping, filters type/from/to, last_event_id replay scoped safely (if last_event_id doesn't belong to requested mission, return empty safely no leak, if not found return from start scoped to mission), deterministic ordering timestamp ASC + id ASC, total count via func.count, pagination.
  - `subscribe(mission_id)` in-process async.

Event types required now: mission_created, mission_status_changed. Prepared for future: task_status_changed, agent_state_changed, tool_call_started, tool_call_completed, tool_call_failed, approval_requested, approval_decided, handoff, error, cost_updated. Do not fabricate other types.

### Event Envelope per Shared Contract
Inspect `packages/shared/src/events.ts` and Phase 2B-1 schemas, no silent different structure.

Required fields: id, type, source, mission_id, task_id nullable, agent_id nullable, timestamp, version, payload, metadata (optional). Our implementation adds agent_run_id nullable per Phase 2B-1 fix (agent_id→agents.id SET NULL + agent_run_id nullable→agent_runs.id SET NULL).

Backend `EventResponse` uses `Field(validation_alias="metadata_")` to avoid conflict with SQLAlchemy Base.metadata (class-level MetaData object). This fixes Pydantic serialization error where metadata field would otherwise pick up Base.metadata instead of column value.

`EventEnvelope` in shared contract has same required fields, plus optional metadata. Backend `EventResponse` and `EventEnvelope` both have from_attributes + populate_by_name.

### Mission API Endpoints
- Location: `app/routers/missions.py`
- Prefix: `/api/v1/missions`
- Bearer Auth: reuse `get_current_user` from `app/dependencies.py` (D4, Authorization: Bearer <NEXUS_DEV_TOKEN> or X-Nexus-Token header, constant-time compare, no query param ?token=, never log token). Single-user MVP: authenticated may access shared dev user data, structured for future per-user auth.
- Error model: {error:{code,message,details}} via DomainError handler and HTTPException handler. Codes: mission_not_found, invalid_transition, validation_error, unauthorized, event_not_found, task_not_found. Map to HTTP 404/400/401, no stack/secrets leak.
- Endpoints:
  - POST /api/v1/missions: validate title/goal/template, default draft, emit mission_created, return 201 MissionResponse
  - GET /api/v1/missions: pagination limit 1-100 default 20 offset >=0, optional status filter (validate against MissionStatus enum, reject invalid with validation_error), optional template filter, deterministic ordering, return PaginatedResponse total+page
  - GET /api/v1/missions/{id}: return {mission: MissionResponse, task_summary: {total, by_status}} 404 typed mission_not_found
  - PATCH /api/v1/missions/{id}: allow explicitly supported fields status, title, validate transition via MissionService, emit mission_status_changed when status changes
  - POST /api/v1/missions/{id}/cancel: idempotent if already cancelled, validate transition to cancelled, persist, emit mission_status_changed
  - GET /api/v1/missions/{id}/tasks: list tasks for mission, verify mission exists, no cross-mission leak, status filter optional, deterministic ordering created_at ASC + id ASC, pagination
  - GET /api/v1/missions/{id}/events: ordered deterministically timestamp ASC + id ASC, filters type (alias type), from, to, limit, offset, last_event_id mandatory scoping, last_event_id replay safe no leak, do NOT implement WS yet (future)
- Do NOT implement /start (deferred to agent execution PR)
- FastAPI structure: app/routers/missions, tasks, events (events via missions router for scoping), services/mission, event_bus, schemas existing+additions, dependencies.py database/authentication, no DB logic in routers, service independently testable.

### DB Reuse Phase 2B-1 Models
Reuse existing models: users, missions, tasks, task_dependencies, agents, agent_runs, events. Do NOT add tool_registry/mcp_servers/tool_permissions/tool_calls/approvals/audit_logs (deferred). Use indexes mission_id filtering efficient, deterministic timestamp+id ordering.

### Frontend Boundary
Do NOT redesign/modify Phase 2A UI. Prefer zero changes. Boundary: Mock Zustand → future adapter → real API+events → future WS. Phase 2A dashboard remains polished futuristic minimal dark, 8 routes static.

### Testing Focused
- test_missions_api: auth (401 without token, 401 invalid token, 200 valid via Authorization and X-Nexus-Token), create (201, title/status/id), validation (400/422 empty title/goal/missing), list pagination (limit/offset deterministic no overlap), status filter (draft filter works, invalid returns validation_error), get (mission + task_summary, 404 mission_not_found), update valid transition (draft→decomposing→planned), invalid transition (draft→running returns invalid_transition), cancel (idempotent), cancel invalid from completed (400 invalid_transition), tasks list (empty, no cross-mission leak, 404 for fake mission), events list (mission_created, filter by type, last_event_id replay).
- test_event_envelope: shared contract exists, backend EventEnvelope matches shared required fields, model has required columns, mission_created structure (type, source, mission_id, payload contains mission_id/title/status), mission_status_changed structure (from/to), deterministic ordering, mission scoping mandatory, last_event_id replay scoped safe (wrong mission returns empty no leak, non-existent handled safely scoped).
- test_mission_service: create success + event emission, validation, lifecycle matrix valid (draft→decomposing→planned→running→paused→running→awaiting_approval→running→completed→archived), invalid (draft→running, draft→completed, running→draft, running→decomposing), terminal no back (completed→running invalid, completed→draft invalid, archived→running invalid, completed→archived valid), cancel idempotent, cancel invalid from completed, get not found, list pagination deterministic no overlap, event emission on status change (mission_created + mission_status_changed with from/to).
- test_event_bus: emit persists, list deterministic ordering, mission scoping, filters, last_event_id replay (after e1 returns e2,e3), last_event_id wrong mission safety (empty no leak), Redis unavailable does not prevent DB persistence (set redis_url to invalid-host, emit still persists), subscriber in-process (async generator receives 2 events).

All tests use sqlite+aiosqlite in-memory, no real Redis/LLM/MCP/LangGraph. 64 tests pass (21 from Phase 2B-1 + 43 new).

### Security Mandatory
- No eval/exec/compile in app code (verified via grep)
- No unrestricted FS/shell, no MCP execution, no hardcoded secrets, no API keys
- No bearer in URLs/logs, validate all request data, mission/event auth boundaries, no exception internals leak
- Bearer token constant-time compare, never logged
- Error responses do not leak stack/secrets

### Documentation
- ADR 014 created
- Architecture.md updated only if needed (frontend unchanged)
- Verification: backend pytest 64 passed, frontend typecheck passed, build 8 routes static, Docker Compose yaml safe_load ok, security scans no eval/exec/compile, no bearer in URLs.

## Consequences
- Mission API + EventBus foundation unblocks next PR (agent execution)
- Postgres authoritative, Redis optional isolated, no event loss when Redis down
- Lifecycle validator explicit, single vocabulary, typed errors
- EventEnvelope aligned with shared contract, deterministic replay safe
- Bearer Auth D4 preserved, error model consistent
- Service independently testable, no DB logic in routers
- Frontend unchanged, Mock→real API boundary clear
- Tests ensure auth, validation, transitions, scoping, replay safety, Redis resilience

## Alternatives Rejected
- Second status vocabulary: rejected, must reconcile single vocabulary
- Redis as authoritative: rejected, Postgres is source of truth
- Losing events when Redis unavailable: rejected, DB persistence must continue
- Bearer token in URL query ?token=: rejected per security, use Authorization header or initial WS auth message
- Implementing /start in this PR: rejected, deferred to agent execution PR
- Implementing LangGraph, real agent execution, ToolRegistry, approval engine, real MCP: rejected, deferred
- Modifying Phase 2A frontend UI/3D: rejected, prefer zero changes
- Adding tool_registry etc tables: rejected, keep scope small per Phase 2B-1
- Eval/exec/compile for dynamic logic: rejected per security

## Non-Goals
- No real agent execution
- No LangGraph orchestration
- No ToolRegistry/tool_calls
- No approval engine
- No real MCP process/network execution
- No WS implementation (only in-process subscriber for tests/future)
- No /start endpoint
- No frontend redesign
