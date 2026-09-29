# ADR 017: Phase 2B ToolRegistry + MCP Boundary + SandboxService

Date: 2026-09-29
Status: Accepted
Phase: 2B-4 ToolRegistry + SandboxService + Permission + Approval Foundation

## Context

Phase 2B-3 introduced Supervisor, DAG, LangGraph, Orchestrator with safe stub AgentRunner. No real tool execution. Phase 2B-4 requires controlled tool/security boundary:

- AgentRunner previously bypassed tool security
- Need abstraction for tool discovery, validation, execution
- SandboxService was placeholder, no path traversal protection
- MCP integration was scaffold, no transport validation, no private network prevention
- No tool call audit trail

Requirements from Phase 2B-4 spec:

- ToolRegistry: register_tool/get_tool/list_tools/validate_tool_arguments/discover MCP tools via isolated boundary
- Tool definition: id/name/description/source/input JSONSchema/output JSONSchema/capability_tags/risk_level/default_permission/sandbox config
- Permission vocab: forbidden/approval_required/auto/read_only_auto
- Seed builtin tools: web_search/read_file/write_file/shell/memory_search/rag_query
- SandboxService: create_workspace/read_file/write_file/exec_command/validate_path, no unrestricted host FS/shell, workspace-scoped, reject traversal/symlink/absolute outside, normalize/validate, shell via SandboxService requires approval
- MCP: transports stdio/streamable_http/sse_legacy (SSE forbidden by default), configured servers only, no arbitrary auto-connect, no arbitrary URLs from prompts, no unrestricted network, discovery isolated via MCPManager, registered in ToolRegistry
- No bypass of ToolRegistry

## Decision

### ToolRegistry

- Table `tool_registry` with id PK string (e.g., web_search), name, description, source (builtin/mcp), mcp_server_id FK nullable, input_schema JSONB, output_schema JSONB, capability_tags JSONB, risk_level enum low/medium/high/critical, default_permission enum, sandbox_config JSONB, timestamps.
- Service `ToolRegistryService` with:
  - `register_tool(session, tool_def)` idempotent upsert
  - `get_tool(session, tool_id)` lookup
  - `list_tools(session, source, risk_level)` listing with filters
  - `validate_tool_arguments(session, tool_id, args)` using jsonschema, output size limits, arg size 10KB limit
  - `discover_mcp_tools(session, mcp_server_id, discovered_tools)` register MCP tools with source=mcp, default risk medium, permission approval_required
  - `seed_builtin_tools(session)` idempotent seed of 6 builtin tools
- Builtin tools seeded:
  - web_search: low risk, auto, controlled stub, network allowlist required, output simulated deterministic
  - read_file: low risk, read_only_auto, SandboxService read_file, workspace-scoped
  - write_file: high risk, approval_required, SandboxService write_file, approval required
  - shell: critical risk, approval_required, ALWAYS approval per D6, container isolation abstraction, no os.system/shell=True
  - memory_search: low risk, auto, interface stub, no full RAG
  - rag_query: low risk, auto, interface stub, no full RAG
- No bypass: AgentRunner must go through ToolRegistry, validated in tests.

### SandboxService

- Abstract interface `SandboxService` with create_workspace(mission_id)/read_file/write_file/exec_command/validate_path
- Implementation `SecureSandboxService`:
  - Base path temp/nexus-sandbox/{mission_id} - in Docker Compose volume-mounted isolation
  - `validate_path`: rejects null bytes, absolute system paths (/etc,/usr,/bin,/sbin,/root,/home,/var,/tmp,/dev,/proc), normalizes via os.path.normpath, checks commonpath inside workspace_root, rejects symlink escape (resolves symlink target, checks inside workspace)
  - `create_workspace`: creates mission_id dir + output/tmp/src subdirs
  - `read_file`: validates path, checks exists+isfile, size limit 1MB, reads utf-8 ignore, output limit 1MB truncation
  - `write_file`: validates path, content limit 1MB, ensures parent exists, writes utf-8, returns redacted absolute path internally
  - `exec_command`: isolated execution abstraction, no os.system, no shell=True, no eval/exec/compile, forbidden patterns (rm -rf /, fork bomb, mkfs, dd if= of=/dev, > /dev/sd, chmod / etc), dangerous substrings check, timeout 1-60s, safe subprocess with shell=False for simple commands without shell operators, simulated container execution for shell operators or not in safe allowlist, output limit 10KB, deterministic for tests, documented boundary: real Docker SDK container isolation in production
  - Safe allowlist for MVP: ls,cat,echo,pwd,whoami,date,head,tail,wc,grep,find,python3,python,node,npm,pip,git status,git log
  - Forbidden: rm -rf /, :(){:|:&};:, mkfs., dd if= of=/dev/, > /dev/sd, chmod / etc
  - No dangerous demo exec
  - If Docker SDK not robust, safe abstraction deterministic test impl, document boundary

### MCP Manager

- Table `mcp_servers` with id UUID, name, transport enum stdio/streamable_http/sse_legacy, command Text (stdio), url Text (http), env JSONB (secret refs not raw), enabled bool, status, last_seen, timestamps, check constraint transport valid
- Service `MCPManager`:
  - `list_servers(session, enabled_only)` 
  - `get_server(session, server_id)`
  - `create_server(session, name, transport, command, url, env, enabled)` with validation: transport enum, stdio requires command, dangerous commands forbidden in stdio, http transports require url http/https, private/internal URL forbidden via is_private_or_internal_url check (loopback, private ranges 10/8,172.16/12,192.168/16, link-local, localhost, 0.0.0.0, ::1, fc00::/7, fe80::/10, internal domains, metadata), no arbitrary URLs from prompts, SSE forbidden by default (documented, allowed creation but flagged)
  - `delete_server`
  - `discover_tools(session, server_id)` isolated discovery, mocked for tests, returns mocked tools if server name contains mock/test, updates last_seen, status, returns tool defs
  - `call_tool(session, server_id, tool_id, args)` isolated boundary, mocked deterministic for MVP, real MCP SDK optional
  - `validate_transport_allowed` returns False for sse_legacy (forbidden by default)
- Tool discovery isolated via MCPManager, discovered tools registered in ToolRegistry via ToolRegistry.discover_mcp_tools boundary
- Configured servers only, enabled flag, no arbitrary auto-connect, no arbitrary URLs from prompts, no unrestricted network
- Remote network policy prevent private/internal via is_private_or_internal_url

### Security

- No eval/exec/compile abuse, no os.system, no unrestricted subprocess, no shell=True
- Path normalization/traversal/symlink/workspace isolation enforced
- Schema validation via jsonschema + size limits
- Secret redaction in logs/results (password, secret, token, api_key, credential)
- Output limits: args 10KB, file 1MB, command output 10KB
- Network allowlist for web_search controlled stub
- Private/internal URL blocking for MCP
- Audit events via EventBus

## Consequences

- ToolRegistry is single source of truth, no bypass
- SandboxService provides secure workspace isolation, deterministic test impl
- MCP boundary safe mocked, real servers optional
- Tests can run without LLM/MCP server/dangerous shell
- Frontend unchanged (Phase 2A preserved)
- Next phase: real Docker SDK container isolation, real MCP SDK integration

## Deferred

- Real Docker SDK container isolation (documented boundary)
- Real MCP SDK client (stdio/streamable_http)
- Real web_search with allowlist
- Full RAG/memory implementation
- WS/frontend approval UI integration
