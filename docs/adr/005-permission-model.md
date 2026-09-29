# ADR 005: Tool Permission Model and SandboxService

**Status:** Accepted (v0.2 Review - SandboxService)
**Date:** 2026-09-29
**Decisions:** D6 Balanced approval, shell always approval

## Context
Need least-privilege, human gates, no unrestricted host access. Review requires SandboxService abstraction and container isolation for exec.

## Decision
- **Permission Levels:** forbidden, approval_required, auto, read_only_auto
- **Scopes:** tool_id, agent_type, mission_id, arg pattern regex, future user role
- **Policy Engine:** JSONB in tool_permissions, evaluation: agent_type + tool_id + args + mission_policy -> decision (allow/deny/require_approval + reason)
- **Default Policy (D6):** Balanced - write to allowed workspace via SandboxService auto if low risk, elsewhere approval, shell always approval, high-risk tools approval_required
- **SandboxService Abstraction (NEW per review):**
  - Interface: create_workspace(mission_id), read_file, write_file, exec_command (container-isolated), cleanup
  - MVP: Scoped workspace dir for file tools, ephemeral container (Docker/gVisor-like) for shell: no network/limited, CPU 0.5, mem 512MB, read-only root except workspace, timeout 30s
  - Agents never receive unrestricted host shell/file access - all via SandboxService
  - No generic chroot /workspace/{mission} assumption, enforced via service
- **Tool Registry:** id, name, description, source (builtin|mcp), mcp_server_id, input_schema, risk_level, default_permission, sandbox_config {service: SandboxService, isolation: container}
- **UX:** Matrix Agent Types x Tools, suggested permissions by risk_level, audit shows checks

## Consequences
- Zero-trust, least-privilege
- Container isolation for exec
- No host escape
- Balanced usability

## Alternatives Rejected
- Raw chroot assumption: insufficient, rejected per review
- Unrestricted host shell: security risk, rejected
- Strict all approval: too many interruptions
- Permissive all auto: unsafe
