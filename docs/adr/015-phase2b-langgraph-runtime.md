# ADR 015: Phase 2B-3 LangGraph Runtime Foundation

**Status:** Accepted
**Date:** 2026-09-29
**PR:** feat/phase2b-supervisor-langgraph (PR 2B-3)
**Decisions:** MissionState, graph structure, DAG validation, checkpoint abstraction, execution mechanism, lifecycle integration

## Context
Phase 2B-2 delivered Mission API + EventBus with Postgres as source of truth, optional Redis, deterministic ordering, mission scoping, last_event_id replay safe. Phase 2B-3 needs first real orchestration pipeline: Mission API → SupervisorService → MissionPlan → DAG validation/planning → Agent assignment → LangGraph execution → Task execution stub → Mission finalization → EventBus.

Must preserve Phase 2A frontend/3D UI unchanged, preserve persistence and Mission API/EventBus, implement only orchestration foundation, no full real-world tool execution yet.

Need to inspect LangGraph version compatibility with Python 3.11.2. Current env has Python 3.11.2, pip shows langgraph 1.2.12 latest, 0.6.x stable. Tested langgraph 0.6.11 installs and StateGraph imports ok with warning about JsonPlusSerializer allowed_objects. Chose 0.6.11 + langchain-core 0.3.67 for stability, avoids fragile 1.x breaking changes, compatible with Python 3.11.

Need checkpointing that can be added cleanly. Options: PostgreSQL-backed via langgraph-checkpoint-postgres 3.x, or in-memory deterministic. For Phase 2B-3, prefer abstraction behind interface, use deterministic test implementation, document choice, do not introduce fragile infrastructure merely to claim checkpoint support.

Need API integration POST /missions/{id}/start that verifies mission exists, valid starting state, invokes orchestration, transitions lifecycle, returns execution info, does not block indefinitely, uses service boundary replaceable by durable worker later.

Need DAG validation utility: dependency validation, cycle detection, topological ordering, task layers for 3D UI, deterministic ordering, clear errors.

Need safe AgentRunner stub that creates agent_run, moves task to running, simulates deterministic result, emits events, completes task, must NOT execute arbitrary shell, host FS, MCP, unrestricted network, bypass PermissionService, eval/exec/compile.

## Decision

### LangGraph Version
- Chose `langgraph==0.6.11` and `langchain-core==0.3.67`
- Tested: `from langgraph.graph import StateGraph` works on Python 3.11.2, only deprecation warning about allowed_objects
- Alternative 1.x (1.2.12) considered but deferred due to potential breaking changes and heavier dependencies
- Original scaffold mentioned 0.2.28, but 0.6.11 is stable and checkpoint-compatible
- Documented in requirements.txt with comment that postgres checkpointing is deferred

### MissionState
- Location: `app/core/langgraph/state.py`
- TypedDict, total=False for flexibility, serializable, checkpoint-friendly
- Fields:
  - mission_id: str
  - goal, title, template, status: str
  - tasks: List[TaskState] where TaskState includes id, title, description, agent_type, status, dependencies, output, error, agent_run_id, token_usage, cost_cents
  - dag: Dict with nodes, edges, layers, topological_order
  - agent_assignments: Dict task_id→agent_type
  - agent_runs: List[AgentRunState] with id, task_id, agent_id, agent_type, status, token_usage, cost_cents
  - messages: Annotated[List[Dict], add] for reducer
  - approvals_pending: List[Dict] placeholder for next phase
  - total_tokens, total_cost_cents, cost_breakdown
  - error, error_details, next_action, metadata, current_task_id, completed_tasks, failed_tasks
- No duplication of unrelated frontend types, only runtime needed

### Graph Structure
- Location: `app/core/langgraph/graph.py`, `app/core/langgraph/nodes/`
- Nodes implemented for this PR:
  - decompose: uses SupervisorService to decompose mission into MissionPlan, converts to TaskState, sets status=decomposing, next_action=plan_dag
  - plan_dag: validates DAG via validate_and_plan_dag, computes layers, topological order, deterministic, sets status=planned, next_action=assign
  - assign: capability-based assignment using keyword scoring, infers agent_type from title/description if invalid, sets agent_assignments, next_action=execute_task
  - execute_task: simulates execution in topological order deterministically, marks tasks completed, updates total_tokens/cost, status=running, next_action=finalize (real DB execution done in orchestrator service outside graph for testability)
  - finalize: determines completed/failed based on error/failed_tasks, status=completed or failed, next_action=None
- Placeholders for next tool/approval phase:
  - evaluate_task: returns next_action=finalize, message placeholder
  - handle_approval: returns next_action=execute_task, placeholder
  - replan: returns next_action=finalize, placeholder
- Graph: decompose → plan_dag → assign → execute_task → finalize, conditional edges for failure path any node can route to finalize on error
- Execution supports multiple independent tasks conceptually via topological order, but actual execution safe and deterministic via stub
- Creation: `create_mission_graph(checkpointer=None)` compiles StateGraph, optional checkpointer param for future, `get_mission_graph()` without checkpointer for tests, `get_mission_graph_with_memory_checkpointer()` uses LangGraph's MemorySaver for checkpoint testing

### DAG Planning
- Location: `app/core/dag.py`
- Functions:
  - validate_dependencies: checks all dependencies exist in task_ids, raises DAGValidationError with details
  - detect_cycle: DFS with sorted neighbors for determinism, returns cycle path if found
  - topological_sort: Kahn's algorithm with sorted queue for determinism, raises DAGValidationError with cycle details if fails
  - compute_layers: layer 0 = no dependencies, layer = max dependency layer +1, for 3D UI
  - validate_and_plan_dag: main entry, checks duplicate ids, validates dependencies, detects cycle, topological sort, computes layers, builds edges sorted deterministically, returns DAGResult nodes, edges, layers, topological_order, has_cycle
  - create_dag_from_plan: returns dict suitable for storing on mission.dag JSONB
- No hidden or random ordering, deterministic, clear errors for invalid DAGs
- Store resulting DAG on mission (missions.dag JSONB)

### Checkpoint Strategy
- Location: `app/core/langgraph/checkpoint.py`
- Abstraction: `CheckpointService` ABC with save_checkpoint, load_checkpoint, delete_checkpoint
- Implementations:
  - InMemoryCheckpoint: deterministic test impl, in-memory dict, store copy, clear method, MVP-only isolated behind interface for durable replacement later
  - PostgresCheckpoint: placeholder for future, holds connection_string, fallback to InMemoryCheckpoint for Phase 2B-3, TODO comment for real PostgresSaver when stable, reason deferred to avoid fragile infrastructure
- Factory: `get_checkpoint_service(backend="memory"|"postgres", connection_string)` returns appropriate impl
- Singleton: `checkpoint_service = get_checkpoint_service(backend="memory")`
- Choice documented: For Phase 2B-3, use InMemoryCheckpoint deterministic, Postgres deferred. Reason: avoid fragile infra, keep tests deterministic, no external DB required for checkpoint tests, langgraph-checkpoint-postgres 3.x exists but not yet stable/testable in current env, can be added cleanly via interface later.
- LangGraph's own MemorySaver used in `get_mission_graph_with_memory_checkpointer()` for testing LangGraph checkpointing itself, separate from our abstraction

### Execution Mechanism
- Location: `app/services/orchestrator.py`
- MVP execution mechanism: synchronous within request for now, but isolated behind orchestrator service boundary so it can be replaced by durable worker/queue later
- Does NOT run long-lived orchestration that would block indefinitely: each node is quick and deterministic (decompose uses deterministic fallback when no API key, plan_dag validates, assign infers, execute_task simulates, finalize decides)
- Flow:
  - Verify mission exists via MissionService.get_mission
  - Verify valid starting state: draft, planned, failed, paused allowed (draft initial, planned already decomposed, failed/paused restartable)
  - Transition draft→decomposing via MissionService.update_mission (emits mission_status_changed)
  - Decompose via SupervisorService.decompose_mission (deterministic fallback if no provider)
  - Validate DAG, store on mission.dag
  - Clear existing tasks if any (for restart), create new Task records from MissionPlan with real UUIDs, map temp id→real UUID, store TaskDependency relationships correctly
  - Transition decomposing→planned, planned→running via MissionService
  - Build initial MissionState with mission_id, goal, title, template, tasks, dag, etc.
  - Run LangGraph via `graph.astream(initial_state)` for state transitions (deterministic, quick)
  - Execute tasks via AgentRunner.run_task in topological order with real DB session (safe stub creates agent_run, moves task running→completed, emits task_status_changed, agent_state_changed, cost_updated)
  - On task failure, emit error event and transition to failed
  - On success, transition running→completed, emit handoff event
  - Return execution info mission_id, status, total_tasks, completed_tasks, dag, final_state
- Failure handling: DAGValidationError → emit error event, transition to failed, return error+details; generic exception → emit error, try to transition to failed, return error
- Ensures agents exist: seeds supervisor/researcher/coder/analyst if not exist via begin_nested savepoint to avoid rollback issues

### Lifecycle
- Reuse existing MissionStatus vocabulary: draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived
- Flow for this PR: draft→decomposing→planned→running→completed, failure running→failed
- Do not invent another vocabulary
- Use MissionService for status changes so EventBus emits proper events

### Event Integration
- Use existing EventBus from PR #4 (Postgres authority, optional Redis, in-process subscriber)
- Emit real events:
  - mission_status_changed via MissionService.update_mission
  - task_status_changed via AgentRunner (pending→running, running→completed)
  - agent_state_changed via AgentRunner (idle→running, running→completed)
  - handoff on mission completion via Orchestrator (supervisor source, summary)
  - error on DAG validation or task failure
  - cost_updated via AgentRunner with token_usage/cost_cents
- Do not fabricate tool or approval events (tool_call_started/completed/failed, approval_requested/decided deferred to PR 2B-4)
- All events match packages/shared/src/events.ts (validated via existing test_event_envelope)

### Database
- Reuse existing models: missions, tasks, task_dependencies, agents, agent_runs, events
- Do NOT introduce tool_registry, mcp_servers, tool_permissions, tool_calls, approvals (deferred to PR 2B-4)
- Create task records from MissionPlan with real UUIDs, store dependency relationships correctly via TaskDependency table (not UUID[] array)
- Use indexes mission_id filtering efficient, deterministic ordering

### API Integration
- Added POST /api/v1/missions/{mission_id}/start in missions router
- Verifies mission exists (404 mission_not_found), valid starting state (400 validation_error if not in draft/planned/failed/paused)
- Invokes orchestrator_service.start_mission
- Returns execution info: mission_id, status, total_tasks, completed_tasks, dag, final_state or error
- MVP execution mechanism documented as synchronous within request but isolated behind service boundary replaceable by durable worker
- Clearly documented in ADR and code comments

## Consequences
- First real orchestration pipeline unblocks next PR (tool/approval)
- LangGraph 0.6.11 stable on Python 3.11, checkpoint abstraction clean, Postgres deferred to avoid fragile infra
- DAG validation deterministic, cycle detection, layers for 3D UI
- AgentRunner safe stub no real shell/FS/MCP/network/eval/exec/compile
- Lifecycle uses single vocabulary, MissionService emits proper events
- Tests ensure deterministic execution, no API key required
- Frontend unchanged, zero modifications

## Alternatives Rejected
- LangGraph 1.x: rejected for Phase 2B-3 due to potential breaking changes, heavier deps, not yet needed
- PostgreSQL-backed checkpointing immediately: rejected, use abstraction with InMemory for determinism, avoid fragile infra, document choice, can add cleanly later
- Running long-lived orchestration directly in HTTP request blocking indefinitely: rejected, each node quick deterministic, isolated behind service boundary for durable worker replacement
- Inventing new lifecycle vocabulary: rejected, reuse existing MissionStatus
- Real tool execution in this PR: rejected, safe stub only, real tools belong to PR 2B-4
- Using eval/exec/compile for dynamic logic: rejected per security
- Modifying frontend: rejected, prefer zero changes

## Non-Goals
- No real tool execution
- No ToolRegistry/tool_calls
- No approval engine (evaluate_task, handle_approval, replan placeholders)
- No real MCP process/network execution
- No RAG pipeline
- No WS implementation beyond existing
- No frontend redesign
