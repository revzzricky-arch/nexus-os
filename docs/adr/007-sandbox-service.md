# ADR 007: SandboxService Abstraction

**Status:** Accepted (v0.2 Review - NEW)
**Date:** 2026-09-29

## Context
Review requires replacing generic chroot assumption with SandboxService abstraction, container isolation for command execution, agents never receive unrestricted host shell/file access.

## Decision
- **Interface:** SandboxService with methods:
  - create_workspace(mission_id) -> workspace_id/path
  - read_file(mission_id, path) -> content
  - write_file(mission_id, path, content) -> result
  - exec_command(mission_id, command, timeout=30s, env) -> result (container-isolated)
  - cleanup(mission_id)
- **MVP Implementation:**
  - File: Scoped directory per mission (e.g., /data/workspaces/{mission_id} or volume), enforced via service, symlink blocking, traversal detection
  - Exec: Ephemeral container (Docker SDK or gVisor-like) with: no network or limited, CPU 0.5, memory 512MB, read-only root except workspace mount, timeout 30s, no privileged, denylist commands (rm -rf /, mkfs, etc.), output size capped, logged, audited
  - No host shell access, no raw chroot assumption
- **Policy:** Allowed paths scoped per mission via SandboxService config, not ad-hoc
- **Integration:** Tool registry sandbox_config references SandboxService, Tool Proxy routes file/shell tools via service, Permission Engine checks before service call
- **Security:** Agents call service API, not host FS/shell directly. All via service.

## Consequences
- Strong isolation
- Clear abstraction, testable
- No unrestricted host access
- Container overhead but acceptable for MVP (exec not high frequency)

## Alternatives Rejected
- Generic chroot /workspace/{mission}: insufficient isolation, rejected per review
- Direct host shell: security risk, rejected
- Full gVisor from day 1: heavy, future option
