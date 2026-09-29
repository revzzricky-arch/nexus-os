# ADR 018: Phase 2B Approval Policy + PermissionService + ToolCall Lifecycle

Date: 2026-09-29
Status: Accepted
Phase: 2B-4 ToolRegistry + SandboxService + Permission + Approval Foundation

## Context

Phase 2B-3 had no approval flow. Phase 2B-4 requires:

- PermissionService: evaluate(agent_type,tool_id,args,mission_policy) returns Decision allow/deny/require_approval reason risk_level evaluated policy, rules forbidden→deny shell ALWAYS approval critical/high→approval_required low-risk read-only→auto where allowed mission overrides respected argument-level rules deterministic prevent bypass ensuring AgentRunner always passes through
- ApprovalService: persistent using approvals table introduce tool_calls only in this PR, methods create_approval/get_approval/list_approvals/decide_approval/expire_approval, statuses pending/approved/denied/expired, record mission/task/agent run/tool call/requested action/args/reasoning/risk level/reviewer/decision/timestamps/comment/edited_args, source of truth Postgres UI never authoritative
- ToolCall model: id/agent_run/task/tool/args/result/status/permission decision/approval_id/latency/timestamps, lifecycle pending→running→success/failed/denied, approval flow pending→approval pending→approved/denied→execution/denied
- Approval flow: Agent requests→ToolRegistry resolves→PermissionService.evaluate→ALLOW execute, REQUIRE_APPROVAL create ToolCall+Approval emit approval_requested wait approve/deny emit approval_decided approved→execute denied→safe denial, use LangGraph foundation cleanly do NOT redesign graph but create interfaces for future handle_approval/re-entry, if cannot safely resume isolate behind ApprovalRuntimeBoundary document for next phase
- EventBus: use existing emit tool_call_started/completed/failed/approval_requested/decided/error follow EventEnvelope persist before realtime
- AgentRunner: update invocation ToolRegistry→PermissionService→ApprovalService→SandboxService/MCPManager→EventBus keep deterministic path safe no unrestricted execution
- API: GET /api/v1/tools, GET /tools/{tool_id}, GET /mcp-servers, POST /mcp-servers, GET /mcp-servers/{id}/tools, DELETE /mcp-servers/{id}, GET /approvals, GET /approvals/{approval_id}, POST /approvals/{approval_id}/decision, GET /tool-calls/{id}, all Bearer auth Pydantic validation mission/user scoping never leak secrets/traces

## Decision

### PermissionService

- Service `PermissionService` with `evaluate(session, agent_type, tool_id, args, mission_id, mission_policy)` → `PermissionDecisionResult` with decision (allow/deny/require_approval), permission enum, reason, risk_level, evaluated_policy dict, requires_approval bool
- Rules deterministic:
  1. Fetch tool, if not found → deny critical
  2. Mission policy overrides: if mission_policy.tool_permissions[tool_id] exists, check override:
     - forbidden → deny
     - approval_required → require_approval
     - auto/read_only_auto → allow BUT shell ALWAYS approval cannot be bypassed even via mission override (D6)
  3. DB tool_permissions: query all for tool_id, filter by specificity score: mission_id match 2, agent_type match 1, both 3, global 0, mission mismatch -1 (not applicable), agent mismatch -1. Sort descending, highest wins. If arg_pattern present, check regex match (re.search) for args, if not matches skip. If matches, use permission but still enforce shell ALWAYS approval.
  4. Default permission from tool registry:
     - ALWAYS_APPROVAL_TOOLS = {shell} → require_approval always per D6 balanced policy
     - forbidden → deny
     - critical/high risk → require_approval
     - approval_required → require_approval
     - auto/read_only_auto + low/medium risk → allow, but read_file suspicious path check (..,/etc/,/root/,/home/,/var/,/usr/,/bin/,/sbin/) → require_approval
     - Fallback → require_approval for safety
- Argument-level rules: _matches_arg_pattern checks regex patterns in arg_pattern JSON, e.g., {"path": "^/workspace/output/.*"}
- Prevent bypass: AgentRunner always passes through PermissionService, validated in tests

### ApprovalService

- Table `approvals` with id UUID, mission_id FK missions.id CASCADE, task_id FK tasks.id CASCADE nullable, agent_run_id FK agent_runs.id CASCADE nullable, tool_call_id FK tool_calls.id SET NULL nullable, type enum tool/task/mission default tool, status enum pending/approved/denied/expired default pending, requested_by string nullable, requested_payload JSONB (action,args,reasoning,risk_level), reviewed_by FK users.id SET NULL nullable, review_comment Text nullable, edited_args JSONB nullable, created_at, reviewed_at, expires_at nullable, indexes mission_id,task_id,agent_run_id,status,tool_call_id
- Table `tool_calls` with id UUID, agent_run_id FK agent_runs.id CASCADE nullable, task_id FK tasks.id CASCADE nullable, tool_id FK tool_registry.id CASCADE, args JSONB, result JSONB nullable, status enum pending/running/success/failed/denied default pending, permission_decision JSONB nullable, approval_id FK approvals.id SET NULL nullable, latency_ms Integer nullable, created_at, updated_at, indexes agent_run_id,task_id,tool_id,approval_id,status
- Circular FK handling: approvals.tool_call_id FK to tool_calls SET NULL, tool_calls.approval_id FK to approvals SET NULL, created via create_table without FK then add FKs via create_foreign_key in migration 002
- Service `ApprovalService`:
  - `create_approval(session, mission_id, task_id, agent_run_id, tool_call_id, type, requested_by, requested_payload, expires_at)` default expiry 24h, creates pending
  - `get_approval(session, approval_id)` lookup
  - `list_approvals(session, mission_id, status, limit, offset)` with total count
  - `decide_approval(session, approval_id, decision, reviewed_by, review_comment, edited_args)` validates decision approved/denied, checks pending status, checks expiry (if expired → set expired and raise ValidationError), sets status, reviewed_by, comment, edited_args, reviewed_at now
  - `expire_approval(session, approval_id)` sets expired if pending
  - `expire_stale_approvals(session)` bulk expire pending past expires_at
  - `get_pending_for_mission(session, mission_id)` list pending for mission
- Source of truth Postgres, UI never authoritative

### ToolCall Lifecycle

- Statuses: pending→running→success/failed/denied, approval flow pending→approval pending→approved/denied→execution/denied
- ToolCall model as above, permission_decision stores evaluated policy
- Approval flow:
  - Agent requests tool via AgentRunner.execute_tool
  - ToolRegistry resolves + validates args
  - PermissionService.evaluate → ALLOW → execute via Sandbox/MCP → EventBus tool_call_started/completed/failed
  - REQUIRE_APPROVAL → create ToolCall pending + Approval pending → emit approval_requested → wait → POST /approvals/{id}/decision → approved → execute with original or edited_args → emit tool_call_completed + approval_decided, denied → safe denial → emit tool_call_failed + approval_decided
  - DENY → ToolCall denied → emit tool_call_failed safe denial
- EventBus uses existing emit, follow EventEnvelope, persist before realtime

### AgentRunner Integration

- `execute_tool(session, mission_id, task_id, agent_run_id, agent_type, tool_id, args, mission_policy)` implements full flow: resolve, validate, create ToolCall pending, emit tool_call_started, evaluate permission, store decision, handle deny/require_approval/allow, execute via _execute_tool_internal, store result, emit completed/failed
- `_execute_tool_internal`: builtin tools: web_search controlled stub deterministic, read_file/write_file/shell via SandboxService, memory_search/rag_query stubs, MCP tools via MCPManager.call_tool, unknown → stub
- `handle_approval_decision(session, approval_id, decision, edited_args)`: fetch approval+tool_call, if approved use edited_args if provided else original, re-validate, execute, emit events, if denied set denied and emit
- `_redact_secrets`: redact password, secret, token, api_key, credential from logs/payloads
- `run_task` preserves Phase 2B-3 safe stub but adds tool_flow note, deterministic

### LangGraph Integration

- Do NOT redesign graph, keep decompose→plan_dag→assign→execute_task→finalize
- Update handle_approval_node to real implementation with ApprovalRuntimeBoundary
- `ApprovalRuntimeBoundary` class with is_approval_required, get_pending_approvals, should_resume, isolates approval waiting logic, documented for next phase
- handle_approval_node: if no pending → resume execute_task, if pending has status pending → status awaiting_approval, next_action awaiting_approval, if all decided → resume execute_task
- Future: will use LangGraph interrupts Human-in-the-loop: `from langgraph.types import interrupt; decision = interrupt({...})`
- If cannot safely resume, isolate behind ApprovalRuntimeBoundary, document for next phase (done)

### API

- GET /api/v1/tools list with source/risk_level filters, Bearer auth, no secret leak
- GET /api/v1/tools/{tool_id} retrieve
- GET /api/v1/mcp-servers list enabled_only filter
- POST /api/v1/mcp-servers create with Pydantic validation, transport enum, private URL check
- GET /api/v1/mcp-servers/{id}/tools discover + register via ToolRegistry
- DELETE /api/v1/mcp-servers/{id}
- GET /api/v1/approvals list with mission_id/status filters, pagination
- GET /api/v1/approvals/{approval_id} retrieve
- POST /api/v1/approvals/{approval_id}/decision with decision approved/denied, comment, edited_args, triggers execution via AgentRunner
- GET /api/v1/tool-calls/{id} retrieve with redaction
- Also GET /api/v1/tools/calls/{id} and GET /api/v1/approvals/tool-calls/{id} for compatibility
- All Bearer auth, Pydantic validation, mission/user scoping, never leak secrets/traces, redaction in responses

### DB Migration

- New Alembic migration 002_phase2b_tool_approval_policy creates only tool_registry/mcp_servers/tool_permissions/tool_calls/approvals, do NOT create new users/missions/replacement event/duplicate agent reuse Phase 2B-1 preserve FK idempotently seed builtin tools/policy
- Circular FK handling as described

## Security

- Extremely strict: no eval/exec/compile abuse, no os.system, no unrestricted subprocess, no shell=True, no arbitrary host FS, no arbitrary MCP URL, no hardcoded credentials, no secrets in logs
- Protections: path normalization/traversal/symlink/workspace isolation, schema validation, permission before exec, shell always approval, high/critical approval, forbidden denied, network allowlist, output limits, secret redaction, audit events, CI scanner intact

## Testing

- test_tool_registry registration/lookup/listing/schema validation/seed idempotency
- test_permission forbidden/shell always approval/critical/high approval/low-risk auto/mission overrides/argument-level
- test_sandbox workspace creation/traversal/absolute escape/symlink escape/safe reads/writes/dangerous shell rejected
- test_approval create/list/approve/deny/expire/edited args/persistence
- test_tool_calls lifecycle/permission integration/approval integration/event emission
- test_mcp_manager stdio/streamable_http/SSE forbidden/mock discovery/no arbitrary auto-connect
- test_tool_api/test_approval_api/test_mcp_api preserve all previous tests

## Consequences

- Controlled tool/security boundary established
- Approval flow persistent, source of truth Postgres
- ToolCall lifecycle audited via EventBus
- AgentRunner no bypass, deterministic safe
- API ready for future WS/frontend integration but frontend ZERO changes per spec
- Deferred: WS/frontend approval UI, real Docker SDK, real MCP SDK, LangGraph interrupt/resume

## Deferred Execution

- Frontend ZERO changes Phase 2A unchanged approval UI mock-backed backend source of truth
- WS/frontend integration deferred
- Real container isolation deferred but boundary documented
- Real MCP SDK deferred but boundary documented
- LangGraph interrupt/resume deferred but ApprovalRuntimeBoundary provides interface
