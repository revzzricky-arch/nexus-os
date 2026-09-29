# ADR 006: MCP Transport - stdio + Streamable HTTP

**Status:** Accepted (v0.2 Review)
**Date:** 2026-09-29

## Context
MCP spec evolved. Legacy SSE is deprecated. Need current spec transport.

## Decision
- **Local MCP servers:** stdio (child process, managed lifecycle)
- **Remote MCP servers:** Streamable HTTP (HTTP POST with streaming response, current MCP spec)
- **SSE:** Mentioned only as legacy compatibility, not used for new design
- **MCP Manager:** Client pool handling both transports, health checks, reconnect, list_tools/resources/prompts on startup, register in Tool Registry
- **DB:** mcp_servers.transport enum: stdio, streamable_http, sse_legacy (legacy only)
- **Security:** Via SandboxService where needed, network allowlist, output size cap 1MB
- **MVP Servers:** Filesystem (stdio, SandboxService scoped), Fetch (Streamable HTTP, allowlist), optional GitHub read-only (Streamable HTTP)

## Consequences
- Current spec compliant
- No legacy SSE dependency
- Clear local vs remote distinction
- Future-proof

## Alternatives Rejected
- SSE as primary: legacy, rejected per review
- HTTP without streaming: not spec compliant
- Custom transport: unnecessary
