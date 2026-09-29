# ADR 020: Phase 3 Durable Worker and Mission Jobs

## Status
Accepted - PR 3.1 feat/phase3-durable-worker

## Context
Phase 2B mission execution was synchronous within HTTP request via `orchestrator_service.start_mission`. This is not durable, blocks API, loses work on restart, and doesn't support retry, idempotency, lease/heartbeat, or multi-worker scaling. Requirement: replace API-owned long-running execution with durable Postgres job system.

## Decision

### Architecture
```
POST /api/v1/missions/{id}/start → JobService → mission_jobs table → Worker → Orchestrator/LangGraph
```

- API returns 202 immediately with `mission_id`, `execution_id`, `job_id`
- No long-running work in request
- Worker is separate async process, not FastAPI background task

### mission_jobs Table
Fields:
- `id` UUID PK
- `mission_id` UUID FK CASCADE
- `execution_id` UUID unique execution identifier
- `idempotency_key` optional client-provided
- `status` enum: pending, running, awaiting_approval, paused, completed, failed, cancelled (CHECK constraint)
- `attempts` int, `max_retries` int default 3
- `payload` JSONB validated (32KB limit, no secrets Bearer/sk- forbidden keys token/bearer_token/api_key/password/secret/authorization)
- `result` JSONB, `error` TEXT
- `locked_at`, `heartbeat_at`, `locked_by` for lease/heartbeat
- `created_at`, `updated_at`

Indexes:
- `status+created_at`
- `mission_id+status`
- `execution_id`
- `idempotency_key`
- `locked_at`, `heartbeat_at`, `locked_by`
- Partial unique: `uq_mission_jobs_one_active_per_mission WHERE status IN ('pending','running','awaiting_approval','paused')` - prevents duplicate starts, fallback when no idempotency key
- Partial index: `ix_mission_jobs_heartbeat_expired WHERE status IN ('running','awaiting_approval','paused')` for stale recovery query

### Idempotency
- Client may send `Idempotency-Key` header
- Stored as `idempotency_key` column
- Unique constraint `UNIQUE (mission_id, idempotency_key)`
- On create_job, if same key exists, return existing job (idempotent)
- Fallback: partial unique one active per mission ensures no duplicate concurrent executions without timestamp-based mechanism (preferred per spec)
- Not timestamp-based, uses DB constraints + client key

### Worker Entry Point Correction (Final PR #8)
- Worker **must** call `orchestrator_service.execute_mission_isolated()` explicitly, not legacy `start_mission()`
- `start_mission()` remains only as legacy/backward-compatible synchronous method delegating to `_execute_mission_core()`
- `_execute_mission_core()` is shared implementation, no duplication
- Test proves worker invokes isolated path and does not invoke legacy path

### Paused-Job Recovery Rule (Final PR #8)
Exact rule for PR 3.1:
- Only `running` jobs with expired lease may recover (crashed worker)
- `paused` jobs intentionally paused by user/system must remain paused unless explicit recovery reason – do NOT auto-convert paused to pending merely because heartbeat is old
- `awaiting_approval` must NOT be treated as crashed running job in this PR because approval resume/checkpointing deferred to PR 3.2/3.6
- Implementation: `recover_stale_jobs()` query filters `status IN ('running')` only, not paused, not awaiting_approval
- Regression tests: paused job not auto-requeued, awaiting_approval not treated as crashed

### JobService Methods
- `create_job(mission_id, idempotency_key, payload)`: validates payload size/secrets, checks idempotency lookup, checks active job exists → ConflictError, creates job with execution_id uuid4, handles IntegrityError race by fetching existing
- `get_job(job_id)`, `get_job_by_execution(execution_id)`, `list_jobs(mission_id, status, limit, offset)`
- `claim_job(worker_id, lease_timeout)`: `SELECT id FROM mission_jobs WHERE status='pending' ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED` then `UPDATE ... SET status='running', locked_by, locked_at=now, heartbeat_at=now, attempts++` atomically. SQLite fallback uses `with_for_update` without SKIP LOCKED.
- `update_job_status(job_id, status, result, error)`: terminal statuses clear lease fields
- `heartbeat_job(job_id, worker_id)`: owner check, updates heartbeat_at, fails if wrong owner or not running
- `release_job(job_id, worker_id, lease_expired)`: only if lease expired or owner matches, moves running→pending or awaiting_approval/paused handling
- `cancel_job(job_id)`: idempotent, terminal statuses no-op, pending/running/awaiting_approval/paused → cancelled, clears lease
- `cancel_jobs_for_mission(mission_id)`: cancels all active jobs
- `recover_stale_jobs(lease_timeout)`: cutoff = now - lease_timeout, finds `status IN ('running','awaiting_approval','paused') AND (heartbeat_at < cutoff OR locked_at < cutoff)`, if attempts < max_retries → pending clear lease, else failed with error lease timeout

Lease/heartbeat:
- `locked_at` set on claim, `heartbeat_at` renewed periodically
- Configurable lease timeout (60s default), heartbeat interval (20s default)
- Recovery only when heartbeat/lease expired, not merely locked_at older than 5m
- Tests: healthy worker NOT reclaimed, crashed expired IS reclaimed

### Worker
- `MissionWorker` class: async, bounded count, configurable ID, polling interval, lease timeout, heartbeat interval, max retries
- No FastAPI background task as durable worker (explicit requirement)
- Methods: `execute_job(session, job_id)` invokes orchestrator isolated method, handles success/failure/retry bounded, emits events; `_heartbeat_loop` periodic renew; `run_once(session)` claim+execute; `run_forever(session_factory)` loop with startup stale recovery
- `worker_id` unique per process (uuid suffix)
- Multi-worker future: each worker has unique ID, all poll same table with FOR UPDATE SKIP LOCKED, only one claims atomically, can run on different hosts same DB, lease/heartbeat prevents duplicate, future replacement with LISTEN/NOTIFY or Redis Streams for lower latency

### Orchestrator Integration
- Existing LangGraph reused, no redesign of graph nodes
- New isolated method `execute_mission_isolated(session, mission_id)` as worker entry point, delegates to `_execute_mission_core`
- `start_mission` now delegates to same core for backward compat (tests)
- Ownership moved HTTP request → Worker
- Worker observes cancellation: checks job status before execution, skips if cancelled, handles cancellation during execution safely

### Mission Start API
- `POST /api/v1/missions/{id}/start` → 202 with `mission_id`, `execution_id`, `job_id`, `status`, `idempotency_key`
- Authenticates, validates state (draft, planned, failed, paused allowed), creates durable job, no block
- Repeated same Idempotency-Key returns existing
- Header `Idempotency-Key` supported via FastAPI Header alias

### Cancellation Integration
- `POST /api/v1/missions/{id}/cancel` validates via MissionService (does not bypass), cancels mission + cancels associated jobs via JobService
- Job cancellation mapping: pending→cancelled, running→cancelled (worker observes stop safely), awaiting_approval→cancelled, completed/failed/cancelled idempotent
- Worker checks job status before/after execution, does not call orchestrator if cancelled

### Restart Recovery
- On API startup (lifespan), `recover_stale_jobs_on_startup` finds lease expired jobs, moves pending or failed based on attempts
- Durable job recovery only, not checkpoint-based resume (deferred to PR 3.2)
- Worker also recovers on startup in `run_forever`

### Shared WS Contract Fix
- Old scaffold: `WSSubscribeMessage { channels: string[], last_event_id }`
- Backend: `WSClientSubscribe { mission_id, last_event_id }` + `WSClientUnsubscribe { mission_id }`
- Fixed `packages/shared/src/events.ts` to use `mission_id + last_event_id`, matching backend `apps/api/app/schemas/websocket.py` and `routers/ws.py`
- Frontend hook `apps/web/lib/ws/useWebSocket.ts` updated to use `mission_id`
- `EventEnvelope` unchanged
- No duplicate incompatible definitions

### Security Preserved
- No eval/exec/compile abuse
- No shell/MCP execution in this PR
- No secrets in payload (validation)
- No bearer token in payload/logs
- Payload size validation 32KB
- Mission/user scoping via mission_id FK
- No arbitrary execution
- CI scanner not weakened

### Tests
- `test_jobs.py`: create, claim concurrent SKIP LOCKED, status, cancellation, heartbeat, stale recovery, retry, idempotency, payload validation, list
- `test_worker.py`: pending execution success, failure, retry bounded, heartbeat, cancellation, expired lease recovery, run_once
- `test_mission_start_api.py`: 202 with IDs, idempotency duplicate, invalid state, missing mission, cancellation, list jobs
- `test_ws_shared_contract.py`: shared protocol matches backend, no channels[], EventEnvelope unchanged

### Verification
- `pytest` full backend
- Migration upgrade/downgrade
- Frontend typecheck and build
- Compose validation
- Security scan import/compile

## Deferred Capabilities
- Checkpoint-based resume (PR 3.2)
- Multi-worker LISTEN/NOTIFY or Redis Streams (future, documented)
- Approval resume (not in this PR)
- Observability metrics for worker (future)
- Real LLM providers, real tools, MCP execution (out of scope)

## Consequences
- Mission execution now durable, survives API restart
- API returns 202 fast, no blocking
- Idempotency prevents duplicate starts
- Lease/heartbeat prevents duplicate execution and recovers crashed workers
- Worker is separate process, scalable horizontally
- Existing orchestrator reused, minimal changes
- WS contract fixed, frontend typecheck passes
