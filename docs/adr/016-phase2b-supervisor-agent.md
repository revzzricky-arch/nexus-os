# ADR 016: Phase 2B-3 Supervisor Agent

**Status:** Accepted
**Date:** 2026-09-29
**PR:** feat/phase2b-supervisor-langgraph (PR 2B-3)
**Decisions:** SupervisorService abstraction, deterministic fallback planner, capability-based assignment, AgentRunner stub, ModelProvider reuse

## Context
Need clean SupervisorService abstraction that is provider-independent, reuses ModelProvider, structured MissionPlan output, Pydantic validation, deterministic fallback when no provider configured, no API key required for tests.

MissionPlan should contain mission_id, tasks, dependencies, agent_type, task descriptions, metadata needed for DAG creation. Deterministic fallback may create simple plans for research/code/analysis/general, keep prompts/configuration concise and configuration-driven.

Need capability-based assignment for foundation agent types supervisor/researcher/coder/analyst, reuse seeded agents from PR #3, no large agent personalities.

Need AgentRunner abstraction safe stub that creates agent_run, moves task to running, simulates deterministic result, emits events, completes task, must NOT execute arbitrary shell, host FS, MCP, unrestricted network, bypass PermissionService, eval/exec/compile. Real tool execution belongs to later PR.

Need ModelProvider reuse and extension only where necessary, support configured provider + deterministic fallback for tests/dev, no API key required for default test path, never hardcode credentials, do not couple LangGraph directly to vendor SDK.

## Decision

### SupervisorService
- Location: `app/services/supervisor.py`
- Method: `async def decompose_mission(mission_id, goal, template, title) -> MissionPlan`
- Requirements met:
  - Provider-independent: uses ModelProvider abstraction via `get_model_provider`, no hardcoded OpenAI/Anthropic/Arena logic
  - Reuse existing ModelProvider: `get_model_provider` factory returns OpenAICompatible (covers Arena via base_url override), Anthropic, Ollama, Deterministic
  - Structured MissionPlan output: Pydantic MissionPlan with mission_id, title, goal, template, tasks, dag, metadata
  - Validate output with Pydantic: `MissionPlan.model_validate` after construction and after provider parsing
  - Deterministic fallback when no provider configured: `_generate_deterministic_plan` creates simple plans, no LLM required
  - Tests must not require real LLM/API key: fallback used when no API key or `feature_real_llm=False`, default test path no key required

- Deterministic fallback templates (concise, configuration-driven):
  - research: Research Objective (researcher) → Analyze Findings (analyst) → Synthesize Report (supervisor)
  - code: Design Solution (supervisor) → Implement Code (coder) → Test Implementation (coder) → Review and Document (analyst)
  - analysis: Collect Data (researcher) → Process Data (analyst) → Perform Analysis (analyst) → Create Visualization (supervisor)
  - general: Understand Goal (supervisor) → Execute Task (researcher) → Finalize (supervisor)
  - Each task has id deterministic from title lower replace spaces with _, title, description with {goal} placeholder, agent_type, dependencies, metadata fallback=True
  - DAG validated via `validate_and_plan_dag`, creates MissionDAG with nodes, edges, layers, topological_order

- Provider path:
  - `_should_use_fallback`: checks if openai_api_key/arena_api_key/anthropic_api_key present, and feature_real_llm flag, if no keys or feature disabled → fallback (no API key required)
  - `_build_system_prompt`: concise configuration-driven, mentions agent types, output JSON schema, no large personalities, mentions tools task_create/task_assign/memory_search/approval_request but no execution
  - `_build_user_prompt`: includes title, goal, template, asks decompose into 3-5 tasks with dependencies, valid DAG, appropriate agent_type, JSON only
  - `_parse_provider_response`: extracts JSON via regex, validates tasks have title, creates MissionPlanTask with id/title/description/agent_type/dependencies, fallback if parsing fails, ensures deterministic fallback on any provider failure (safe for tests, no secrets in logs)
  - On provider failure, fallback with metadata fallback_reason truncated to 200 chars, no secrets

- Additional methods:
  - `plan_dag(mission_plan)`: converts plan tasks to DAG format, validates via `validate_and_plan_dag`, returns MissionDAG
  - `assign_tasks(mission_plan)`: capability-based assignment foundation, returns task_id→agent_type mapping, uses agent_type from plan if valid, otherwise infers from title/description keywords (research/gather/collect/find/search→researcher, code/implement/develop/program/build→coder, analyze/analysis/data/process/visualize→analyst, else supervisor), no large personalities

### MissionPlan
- Location: `app/schemas/mission.py`
- Enhanced from Phase 2B-1:
  - MissionPlanTask: id optional (temp id for DAG planning or real UUID after persistence), title, description, agent_type with description, dependencies list, input optional, metadata optional dict
  - MissionPlan: mission_id optional UUID, title optional, goal optional, template optional MissionTemplate, tasks List[MissionPlanTask], dag optional MissionDAG, metadata optional dict, method `to_dag_tasks()` converts to DAG validation format
  - MissionDAG: nodes List[Any] (UUID or string for plan phase), edges List[dict] {from,to}, layers optional dict, topological_order optional List[Any]
- Contains required: mission_id, tasks, dependencies, agent_type, task descriptions, metadata needed for DAG creation (fallback, template, provider)
- Pydantic validation ensures structured output, provider-independent

### DAG Planning
- Location: `app/core/dag.py`
- Already documented in ADR 015, but supervisor uses it for fallback and provider path
- Deterministic fallback never has cycle by construction (research→analyze→synthesize etc linear or with branching but no cycles)
- Provider output validated via DAG validation, clear errors for invalid DAGs

### Task Assignment
- Location: `app/core/langgraph/nodes/assign.py` and `app/services/supervisor.py`
- Foundation agent types: supervisor, researcher, coder, analyst (from seeded agents PR #3)
- Capability-based assignment: uses CAPABILITY_KEYWORDS dict configuration-driven, no large personalities
  - researcher keywords: research, gather, collect, find, search, investigate, explore, objective, understand
  - coder keywords: code, implement, develop, program, build, create, write, test, review
  - analyst keywords: analyze, analysis, data, process, visualize, report, synthesize, findings, insights
  - supervisor keywords: plan, coordinate, manage, design, finalize, document, synthesize, understand, goal
- Example: research-related tasks → researcher, code-related tasks → coder, analysis/data tasks → analyst, planning/coordination → supervisor
- Reuse seeded agents: agents table has unique type, role, system_prompt_template concise (<1000 chars), model_config, tools, capability_tags, seeded via `app/db/seed.py` idempotent
- Assignment logic: if plan's agent_type valid, use it; else infer via keyword scoring, highest score wins, default supervisor
- Deterministic, no randomness

### AgentRunner
- Location: `app/services/agent_runner.py`
- Abstraction: `AgentRunnerService` with `event_bus` dependency, safe stub for Phase 2B-3
- Method: `async def run_task(session, mission_id, task_id, agent_type) -> Dict`
- Safe stub may:
  - create agent_run with id, mission_id, task_id, agent_id (fetch by type, create placeholder if not exists via begin_nested savepoint to avoid rollback issues, ensure NOT NULL constraint satisfied), status running, token_usage 0, cost_cents 0
  - move task to running: from_status → running, update updated_at, emit task_status_changed
  - emit agent_state_changed idle→running
  - simulate deterministic result via `_simulate_result`: based on agent_type, returns dict with type, summary, findings/files/insights/decisions, deterministic True, no real LLM, no shell, no FS, no MCP, no network
    - researcher: type research, summary, findings list, sources []
    - coder: type code, summary, files list, tests_passed True
    - analyst: type analysis, summary, insights, metrics score 0.95
    - supervisor: type coordination, summary, decisions
  - complete task: output = simulated, status completed, token_usage = len(title)+len(description) deterministic, cost_cents 1, update updated_at
  - update agent_run status completed, token_usage, cost_cents
  - emit task_status_changed running→completed, agent_state_changed running→completed, cost_updated with token_usage/cost_cents
  - Return dict task_id, agent_run_id, status completed, output, token_usage, cost_cents
- Must NOT:
  - execute arbitrary shell (no subprocess, os.system, shell=True)
  - access host filesystem (no open with unrestricted paths)
  - connect to arbitrary MCP servers (no MCP client)
  - perform unrestricted network calls (no httpx/requests to arbitrary URLs)
  - bypass PermissionService (not used in this PR, but structure preserved)
  - use eval/exec/compile (verified via grep, no builtin)
- Real tool execution belongs to later tool/approval PR (PR 2B-4)
- Additional: `get_agent_state` fetches AgentRun by id, returns state dict
- Singleton with EventBus dependency

### ModelProvider
- Location: `app/core/model_provider.py`
- Reuse existing abstraction from scaffold (D1 custom lightweight interface)
- Supports:
  - configured provider: OpenAICompatible (covers OpenAI, Arena via base_url override), Anthropic, Ollama
  - deterministic fallback for tests/dev: DeterministicProvider (new) returns valid MissionPlan JSON with 3 tasks, no API key required
  - No API key required for default test path: SupervisorService._should_use_fallback checks if no keys and feature_real_llm=False → fallback, tests set feature_real_llm=False and no keys
  - Never hardcode credentials: all secrets via settings (openai_api_key, arena_api_key, anthropic_api_key, etc. from env), no hardcoded keys in code
  - Do not couple LangGraph directly to vendor SDK: LangGraph nodes use SupervisorService which uses ModelProvider abstraction, not direct vendor SDK
- Factory: `get_model_provider(provider_name)` supports openai-compatible, anthropic, ollama, deterministic, default openai-compatible
- ChatMessage, ChatResponse models remain same, usage tracking, cost_cents

### Security
- No eval, exec, compile (verified via grep, only mentions in docstrings as forbidden)
- No arbitrary shell execution (no subprocess)
- No unrestricted filesystem access
- No arbitrary MCP
- No unrestricted network
- No hardcoded API keys (all via settings from env)
- No secrets in logs (fallback_reason truncated, no token logging)
- Validate all model/provider output via Pydantic MissionPlan.model_validate and DAG validation
- Use existing Bearer authentication (D4) for API endpoints
- Mission ownership/scoping preserved via mission_id mandatory scoping in all queries

## Consequences
- SupervisorService clean abstraction, provider-independent, deterministic fallback safe for tests
- MissionPlan structured, validated, contains all needed for DAG creation
- Capability-based assignment reuses seeded agents, no large personalities, configuration-driven
- AgentRunner safe stub no real execution, emits proper events, deterministic
- ModelProvider reused, deterministic provider for tests, no API key required
- Unblocks orchestration pipeline, ready for tool/approval phase

## Alternatives Rejected
- Hardcoding OpenAI/Anthropic/Arena-specific logic in Supervisor: rejected, use ModelProvider abstraction
- Large agent personalities: rejected, keep concise configuration-driven prompts, capability_tags from seed
- Real shell/FS/MCP/network execution in Phase 2B-3: rejected, safe stub only
- Using eval/exec/compile for dynamic task generation: rejected per security
- Requiring API key for tests: rejected, deterministic fallback no key required
- Coupling LangGraph directly to vendor SDK: rejected, use ModelProvider abstraction
- Creating second agent type vocabulary: rejected, reuse existing AGENT_TYPES from shared

## Non-Goals
- No real tool execution
- No ToolRegistry
- No approval engine (placeholders only)
- No real MCP
- No RAG
- No large personalities
- No hardcoded credentials
