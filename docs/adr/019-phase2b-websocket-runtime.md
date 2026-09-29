# ADR 019: Phase 2B Real-Time WebSocket Runtime

Date: 2026-09-29
Status: Accepted
Branch: feat/phase2b-realtime-runtime

## Context

Phase 2A built Mission Control UI with 3D hybrid orbital + layered DAG, mock runtime data, Zustand store.
Phase 2B-2 introduced EventBus with Postgres as source of truth, in-process subscriber registry, optional Redis abstraction.
Phase 2B-3/4 added supervisor, tool approval policy with ownership enforcement.

Need real-time boundary: Postgres Events → EventBus → WebSocket Manager → Authenticated WS `/api/v1/ws` → Frontend Event Adapter → Zustand Runtime Store → Mission Control 2D + 3D visualization.

Must preserve Phase 2A UI/3D, no redesign, only visible change is runtime data from real backend.

## Decision

### 1. WebSocket Contract

- Endpoint: `WS /api/v1/ws` (also legacy `/ws` for backward compat)
- Auth: first client message `{"type":"auth","token":"<NEXUS_DEV_TOKEN>"}` → `{"type":"auth_ok"}` or `{"type":"auth_error","code":...,"message":...}`
- No token in query/path/logs, constant-time compare via `hmac.compare_digest`
- Server welcome: `{"type":"welcome","message":"NEXUS WS - send auth first","version":1}`

Client messages:
- `auth`
- `subscribe` `{"type":"subscribe","mission_id":"<uuid>","last_event_id":"<optional>"}`
- `unsubscribe`
- `ping`

Server messages:
- `welcome`, `auth_ok`, `auth_error`, `subscribed` (with replay_count), `unsubscribed`, `pong`, `error` (code/message)
- Event stream: raw `EventEnvelope` JSON per `packages/shared/src/events.ts`

### 2. Connection Lifecycle

`CONNECTING → AUTHENTICATING → AUTHENTICATED → SUBSCRIBED → CLOSED`

- AUTHENTICATING with timeout 10s, else `auth_timeout` error and close 1008
- Heartbeat: client ping, server pong, interval 30s
- Clean disconnect: remove from tracking, reverse index cleanup
- Bounded resources: MAX_CONNECTIONS_PER_PROCESS 100, MAX_SUBS_PER_SOCKET 10, MAX_MESSAGE_SIZE 32KB
- No token logging, deterministic errors with codes, no stack traces to client

### 3. Mission Subscription

- Validate authenticated user
- Validate mission exists via `mission_service.get_mission`
- Ownership: if `mission.user_id` is None → allow dev user (scaffold missions); if not None → require exact match with authenticated dev user UUID (fail-closed, same as approval scoping). Prevents unauthorized access.
- Validate `last_event_id` belongs to same mission if supplied: query Event table, if belongs to different mission → `last_event_wrong_mission` error, no leak
- Replay missed events from Postgres via EventBus `list(mission_id, last_event_id)` deterministic order timestamp ASC + id ASC
- Register live subscription after validation, before sending replay to avoid gap
- No cross-mission leak: filter broadcast by mission_id, drop events for other missions

### 4. Event Stream

Use existing EventEnvelope:
```
id, type, source, mission_id, task_id nullable, agent_id nullable, timestamp, version, payload, metadata
```

Supported types: mission_created, mission_status_changed, task_status_changed, agent_state_changed, handoff, error, cost_updated, tool_call_started/completed/failed, approval_requested/decided, message_created, memory_created etc.

Transmit serialized envelope, no wrapper.

### 5. Event Replay Consistency Model

**Source of truth**: Postgres events table

**Replay mechanism**: `EventBusService.list(mission_id, last_event_id, limit, offset)` with deterministic ordering `timestamp ASC, id ASC`

**Flow**:
1. Client sends `subscribe` with optional `last_event_id`
2. Server validates mission ownership and last_event_id scoping
3. Server loads historical events after `last_event_id`:
   - If `last_event_id` is None → from beginning (bounded by MAX_REPLAY_BATCH 100)
   - If `last_event_id` exists and belongs to mission → `WHERE (timestamp > last.timestamp) OR (timestamp == last.timestamp AND id > last.id)`
   - If `last_event_id` not found → from beginning (safe, still scoped to mission)
   - If `last_event_id` belongs to different mission → error, return empty, no leak
4. Server registers live subscription in `websocket_manager` (mission_id → set(connection_id))
5. Server sends `subscribed` ack with replay_count
6. Server sends replay events in order, updating `last_event_ids` tracking per connection to avoid duplicate at boundary
7. Future live events via `broadcast_event` use same tracking, updating last_event_id after send

**Deduplication at boundary**: last_event_id tracking ensures replay events update tracking before live broadcast starts. Live broadcast checks tracking but does not re-send already replayed IDs.

**Mandatory mission scoping**: All queries filter by `mission_id`. `list` checks last_event_id's mission_id to prevent cross-mission leak.

**Bounded batch**: MAX_REPLAY_BATCH 100 to prevent OOM, documented as MVP limit.

### 6. WebSocket Manager

File: `app/services/websocket_manager.py`

Responsibilities:
- Connection registration with bounded limit
- Auth state tracking (CONNECTING, AUTHENTICATING, AUTHENTICATED, SUBSCRIBED, CLOSED)
- Mission subscriptions reverse index `mission_id → set(conn_id)`
- `broadcast_event(event)` → serialize once, send to all subscribed conns for that mission, handle disconnected clients gracefully (no crash)
- `disconnect(conn_id)` → cleanup subscriptions and reverse index
- `cleanup()` → for shutdown
- Constant-time compare, no token logging

No complex business logic, no MCP, no shell.

Redis NOT required: in-process subscriptions acceptable, Postgres source of truth. Future Redis adapter can be isolated behind manager boundary.

### 7. FastAPI Route

File: `app/routers/ws.py`, mounted at `/api/v1/ws` and legacy `/ws`

Responsibilities:
- Accept
- Auth handshake with timeout
- Parse typed client messages (JSON, size check, type check)
- Subscribe/unsubscribe with ownership + replay
- Forward events via manager
- Clean close, no stack traces, typed protocol errors

No business logic beyond validation and replay orchestration.

### 8. Frontend Event Adapter

Files:
- `apps/web/lib/runtime/websocket-client.ts`
- `apps/web/lib/runtime/event-adapter.ts`
- `apps/web/lib/runtime/types.ts`
- `apps/web/lib/runtime/providers.tsx`

Responsibilities:
- Connect/authenticate/subscribe
- Reconnect bounded exponential backoff: initial 1s, multiplier 2, max 30s, max attempts 10, reset after auth success, avoid tight loops
- Maintain last_event_id while mission session active (in-memory, could be sessionStorage for reload)
- Dispatch EventEnvelope into Zustand via adapter
- Disconnect cleanly

No WS code in UI components - isolated in runtime lib.

### 9. Zustand Migration

Keep Phase 2A mock usable, introduce source boundary:

- `MockRuntimeProvider` vs `RealtimeRuntimeProvider` same store shape (missions, agents, tasks, tools, approvals, events, activeMission)
- UI agnostic mock/REST/WS - components use `useRuntimeStore` unchanged
- Runtime mode `mock` / `realtime`, default safe `mock`
- `RuntimeProvider` wraps app in layout.tsx, default mock
- `useRuntime()` hook for connection state, `useRuntimeMode()` for toggle
- `setRuntimeMode`, `setLastEventId`, `setRealtimeConnected` added to store

Do not remove mock yet.

### 10. 3D Integration

Do not redesign 3D scene. Map real events to existing visual state:

- `mission_status_changed` / `mission_created` → core (MissionHeader, progress, phase)
- `agent_state_changed` → AgentNode (state, recent_activity, orbit)
- `task_status_changed` → TaskNode (status, progress, layer)
- `handoff` → edge activity (from_agent recent_activity, to_agent recent_activity)
- `tool_call_started/completed/failed` → tool activity (call_count, latency, agent recent_activity)
- `approval_requested/decided` → gate (ApprovalModal, approvals list, no frontend-only override)
- `error` → error state (agent FAILED, task FAILED)
- `cost_updated` → metrics (activeMission cost_cents, token_usage)

Restrained visual language, no gaming, no excessive neon, no excessive animations.

### 11. Approval UI Boundary

Do not redesign ApprovalModal. Connect future data source to real backend approvals via event adapter. UI shape preserved. No frontend-only override - backend truth authoritative. `approval_decided` updates status via adapter, not direct store mutation.

### 12. Reconnection

- Bounded exponential backoff, max delay 30s
- Reset after auth success
- Avoid tight loops via max attempts 10 and clear timers
- Persist last_event_id while mission session active (sessionLastEventId)
- On reconnect: auth + resubscribe with last_event_id + replay

### 13. Backend Failure Handling

WS failures must not crash FastAPI:

- Invalid JSON → `invalid_json` error, continue
- Invalid type → `invalid_message_type`
- Auth timeout → `auth_timeout`, close 1008
- Invalid token → `auth_invalid_token`, close 1008, no reconnect
- Unknown mission → `mission_not_found`
- Unauthorized → `unauthorized`
- Invalid last_event_id → `invalid_last_event_id`
- last_event_id wrong mission → `last_event_wrong_mission`
- Oversized → `message_too_large`, close 1009
- Disconnected client → log debug, continue, no crash
- Typed protocol errors with code/message, no stack traces

### 14. Rate/Resource Limits (MVP)

Documented:

- MAX_MESSAGE_SIZE 32KB
- AUTH_TIMEOUT 10s
- MAX_SUBS_PER_SOCKET 10
- MAX_CONNECTIONS_PER_PROCESS 100
- MAX_REPLAY_BATCH 100
- HEARTBEAT_INTERVAL 30s
- BACKOFF initial 1s, max 30s, multiplier 2, max attempts 10

### 15. Redis

Do not make mandatory. Source of truth Postgres. In-process subs acceptable. Optionally isolate future Redis pub/sub adapter behind manager. Realtime must not depend on Redis. Current implementation: EventBus tries Redis publish but swallows errors, DB remains source. WebSocketManager uses in-process broadcast.

### 16. Security

- No token in URL, no token logging, constant-time compare
- Ownership enforcement via mission.user_id check
- Event scoping mandatory, no cross-mission replay
- No eval/exec/compile abuse, no shell/MCP, no secret leakage
- Preserve CI scanner: no subprocess, no os.system, no shell=True, no eval
- Errors deterministic, no stack traces

### 17. Testing

Backend:

- `test_websocket_auth.py`: valid/invalid/missing/timeout, no token in URL, constant-time compare
- `test_websocket_protocol.py`: invalid JSON/type, ping/pong, subscribe invalid mission, not found, oversized, too many subs
- `test_websocket_replay.py`: replay order deterministic, last_event_id, wrong mission, no leak, boundary no duplicate, batch bounded
- `test_websocket_events.py`: mission/task/agent/tool/approval/error envelope shape, manager broadcast unit test

Frontend:

- `websocket-client.test.ts`: backoff, last_event_id persistence, no token in URL, mission scoping, mock-realtime boundary
- `event-adapter.test.ts`: mission_status→core, agent_state→AgentNode, task_status→TaskNode, handoff→edge, tool_call→tool activity, approval→gate, restrained visual

Preserve all existing tests: 165+ previous suite.

### 18. API/Event Contract

Authoritative: `packages/shared/src/events.ts` defines EventEnvelope

New protocol types in `app/schemas/websocket.py` separated, not changing EventEnvelope semantics

Frontend types in `apps/web/lib/runtime/types.ts` mirrors backend

### 19. Frontend Visual

Preserve premium futuristic design: dark, minimal, polished, responsive, no redesign 3D/Mission Control, no gaming, no excessive neon glow, no clutter. Only visible change runtime data from real backend via adapter.

### 20. Verification

- Backend: full pytest + WS tests + import + security scan (no eval/exec/subprocess in new code)
- Frontend: typecheck + build + adapter tests
- Infra: docker-compose validation
- All existing tests pass, new tests pass, Phase2A preserved, no scanner weakening, no real MCP/LLM requirement

## Consequences

- Real-time runtime now functional via WS, but still mock default safe
- Future: switch default to realtime when backend stable, or add toggle in UI
- Redis adapter can be added later behind manager without breaking contract
- 3D mapping restrained, no redesign needed

## Alternatives Considered

- SSE: rejected, use WebSocket per spec, SSE legacy only
- Token in URL: rejected per security
- Redis mandatory: rejected, Postgres source of truth
- Redesign 3D: rejected, preserve Phase 2A

## References

- PR #4 EventBus replay `subscribe(mission_id,last_event_id)`
- PR #6 Tool approval ownership enforcement
- Phase 2A Mission Control UI
- `packages/shared/src/events.ts` authoritative contract
