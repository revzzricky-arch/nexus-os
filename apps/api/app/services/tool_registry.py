"""
Tool Registry Service - Phase 2B-4 Real Implementation

Required capabilities:
- register_tool
- get_tool
- list_tools
- validate_tool_arguments
- discover/register MCP tools through isolated MCP boundary

Tool definition includes id, name, description, source, input/output JSONSchema, capability_tags, risk_level, default_permission, sandbox config
Permission vocabulary: forbidden, approval_required, auto, read_only_auto
Seed builtin tools: web_search, read_file, write_file, shell, memory_search, rag_query
"""

import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tool import ToolRegistry, MCPServer
from app.schemas.tool import ToolDefinition, ToolSource, ToolRiskLevel, ToolPermissionType


# Builtin tools definitions - foundational, no bypass
BUILTIN_TOOLS: List[Dict[str, Any]] = [
    {
        "id": "web_search",
        "name": "Web Search",
        "description": "Search web for information (controlled/stub implementation, allowlist enforced)",
        "source": "builtin",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "results": {"type": "array", "items": {"type": "object"}},
                "query": {"type": "string"},
            },
        },
        "capability_tags": ["search", "web", "read_only"],
        "risk_level": "low",
        "default_permission": "auto",
        "sandbox_config": {"requires_network": True, "allowlist_required": True},
    },
    {
        "id": "read_file",
        "name": "Read File",
        "description": "Read file via SandboxService, workspace-scoped only, no unrestricted host FS",
        "source": "builtin",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path within workspace"},
                "mission_id": {"type": "string", "format": "uuid"},
            },
            "required": ["path"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "path": {"type": "string"},
                "size": {"type": "integer"},
            },
        },
        "capability_tags": ["filesystem", "read", "sandbox"],
        "risk_level": "low",
        "default_permission": "read_only_auto",
        "sandbox_config": {"service": "SandboxService", "operation": "read_file", "workspace_scoped": True},
    },
    {
        "id": "write_file",
        "name": "Write File",
        "description": "Write file via SandboxService, workspace-scoped only, approval required for safety",
        "source": "builtin",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path within workspace"},
                "content": {"type": "string", "description": "File content"},
                "mission_id": {"type": "string", "format": "uuid"},
            },
            "required": ["path", "content"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "path": {"type": "string"},
                "size": {"type": "integer"},
            },
        },
        "capability_tags": ["filesystem", "write", "sandbox"],
        "risk_level": "high",
        "default_permission": "approval_required",
        "sandbox_config": {"service": "SandboxService", "operation": "write_file", "workspace_scoped": True, "approval_required": True},
    },
    {
        "id": "shell",
        "name": "Shell",
        "description": "Shell execution via SandboxService container isolation, ALWAYS requires approval per D6 balanced policy, isolated execution abstraction",
        "source": "builtin",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "mission_id": {"type": "string", "format": "uuid"},
                "timeout": {"type": "integer", "default": 30, "minimum": 1, "maximum": 60},
            },
            "required": ["command"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "output": {"type": "string"},
                "exit_code": {"type": "integer"},
            },
        },
        "capability_tags": ["shell", "execution", "critical", "sandbox"],
        "risk_level": "critical",
        "default_permission": "approval_required",
        "sandbox_config": {
            "service": "SandboxService",
            "operation": "exec_command",
            "isolation": "container",
            "approval_required": True,
            "always_approval": True,
            "note": "No host shell, container isolation, no os.system, no shell=True",
        },
    },
    {
        "id": "memory_search",
        "name": "Memory Search",
        "description": "Search mission memory (interface/stub, no full implementation)",
        "source": "builtin",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mission_id": {"type": "string", "format": "uuid"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "results": {"type": "array", "items": {"type": "object"}},
            },
        },
        "capability_tags": ["memory", "search", "read_only"],
        "risk_level": "low",
        "default_permission": "auto",
        "sandbox_config": {"requires_memory": True},
    },
    {
        "id": "rag_query",
        "name": "RAG Query",
        "description": "Query RAG knowledge base (interface/stub, no full RAG pipeline)",
        "source": "builtin",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "collection_id": {"type": "string", "format": "uuid"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "chunks": {"type": "array", "items": {"type": "object"}},
                "citations": {"type": "array", "items": {"type": "string"}},
            },
        },
        "capability_tags": ["rag", "search", "read_only"],
        "risk_level": "low",
        "default_permission": "auto",
        "sandbox_config": {"requires_rag": True},
    },
]


class ToolRegistryService:
    """
    Real ToolRegistry abstraction - no bypass
    """

    async def register_tool(
        self,
        session: AsyncSession,
        tool_def: Dict[str, Any],
    ) -> ToolRegistry:
        """Register tool, idempotent"""
        result = await session.execute(select(ToolRegistry).where(ToolRegistry.id == tool_def["id"]))
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            for key, value in tool_def.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await session.flush()
            await session.refresh(existing)
            return existing

        tool = ToolRegistry(
            id=tool_def["id"],
            name=tool_def["name"],
            description=tool_def["description"],
            source=tool_def.get("source", "builtin"),
            mcp_server_id=tool_def.get("mcp_server_id"),
            input_schema=tool_def["input_schema"],
            output_schema=tool_def.get("output_schema"),
            capability_tags=tool_def.get("capability_tags", []),
            risk_level=tool_def.get("risk_level", "low"),
            default_permission=tool_def.get("default_permission", "auto"),
            sandbox_config=tool_def.get("sandbox_config"),
        )
        session.add(tool)
        await session.flush()
        await session.refresh(tool)
        return tool

    async def get_tool(
        self,
        session: AsyncSession,
        tool_id: str,
    ) -> Optional[ToolRegistry]:
        result = await session.execute(select(ToolRegistry).where(ToolRegistry.id == tool_id))
        return result.scalar_one_or_none()

    async def list_tools(
        self,
        session: AsyncSession,
        source: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> List[ToolRegistry]:
        query = select(ToolRegistry)
        if source:
            query = query.where(ToolRegistry.source == source)
        if risk_level:
            query = query.where(ToolRegistry.risk_level == risk_level)
        query = query.order_by(ToolRegistry.id.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

    async def validate_tool_arguments(
        self,
        session: AsyncSession,
        tool_id: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate tool arguments against JSONSchema
        Returns validated args or raises ValidationError
        """
        from app.core.exceptions import ValidationError
        import jsonschema

        tool = await self.get_tool(session, tool_id)
        if not tool:
            raise ValidationError(f"Tool {tool_id} not found", details={"tool_id": tool_id})

        schema = tool.input_schema
        try:
            jsonschema.validate(instance=args, schema=schema)
        except jsonschema.ValidationError as e:
            raise ValidationError(
                f"Invalid arguments for tool {tool_id}: {e.message}",
                details={"tool_id": tool_id, "error": e.message, "schema": schema},
            )
        except Exception as e:
            # If jsonschema not available or other error, do basic required check
            required = schema.get("required", [])
            for req in required:
                if req not in args:
                    raise ValidationError(
                        f"Missing required argument {req} for tool {tool_id}",
                        details={"tool_id": tool_id, "missing": req},
                    )

        # Additional security checks: output size limits, arg size limits
        # Prevent huge args that could be abuse
        args_str = str(args)
        if len(args_str) > 10000:  # 10KB limit for args
            raise ValidationError(
                f"Tool arguments too large for {tool_id}",
                details={"tool_id": tool_id, "size": len(args_str)},
            )

        return args

    async def discover_mcp_tools(
        self,
        session: AsyncSession,
        mcp_server_id: uuid.UUID,
        discovered_tools: List[Dict[str, Any]],
    ) -> List[ToolRegistry]:
        """
        Discover/register MCP tools through isolated MCP boundary
        Discovered tools registered in ToolRegistry with source=mcp
        """
        registered = []
        for tool_def in discovered_tools:
            # Ensure MCP tools have proper risk level and permission
            # Default MCP tools to approval_required for safety unless explicitly low risk
            tool_def.setdefault("source", "mcp")
            tool_def.setdefault("mcp_server_id", mcp_server_id)
            tool_def.setdefault("risk_level", "medium")
            tool_def.setdefault("default_permission", "approval_required")

            # Validate required fields
            if "id" not in tool_def or "name" not in tool_def or "input_schema" not in tool_def:
                continue

            tool = await self.register_tool(session, tool_def)
            registered.append(tool)

        return registered

    async def seed_builtin_tools(
        self,
        session: AsyncSession,
    ) -> List[ToolRegistry]:
        """Seed foundational builtin tools idempotently"""
        seeded = []
        for tool_def in BUILTIN_TOOLS:
            tool = await self.register_tool(session, tool_def)
            seeded.append(tool)
        return seeded


tool_registry_service = ToolRegistryService()
