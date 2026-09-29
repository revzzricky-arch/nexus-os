"""
Tool Registry + MCP Servers + Tool Permissions + Tool Calls + Approvals
Phase 2B-4 ToolRegistry + SandboxService + Permission + Approval Foundation
"""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Text, DateTime, Integer, Boolean, func, CheckConstraint, ForeignKey, UniqueConstraint, Uuid, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

# Enums matching architecture
TOOL_SOURCES = ("builtin", "mcp")
TOOL_RISK_LEVELS = ("low", "medium", "high", "critical")
TOOL_PERMISSIONS = ("forbidden", "approval_required", "auto", "read_only_auto")
MCP_TRANSPORTS = ("stdio", "streamable_http", "sse_legacy")
TOOL_CALL_STATUSES = ("pending", "running", "success", "failed", "denied")
APPROVAL_TYPES = ("tool", "task", "mission")
APPROVAL_STATUSES = ("pending", "approved", "denied", "expired")


class ToolRegistry(Base):
    __tablename__ = "tool_registry"
    __table_args__ = (
        CheckConstraint(f"source IN {TOOL_SOURCES}", name="ck_tool_registry_source_valid"),
        CheckConstraint(f"risk_level IN {TOOL_RISK_LEVELS}", name="ck_tool_registry_risk_valid"),
        CheckConstraint(f"default_permission IN {TOOL_PERMISSIONS}", name="ck_tool_registry_permission_valid"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g., web_search
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="builtin")
    mcp_server_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True)
    input_schema: Mapped[Any] = mapped_column(JSON, nullable=False)
    output_schema: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    capability_tags: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # JSON array
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="low")
    default_permission: Mapped[str] = mapped_column(String(50), nullable=False, default="auto")
    sandbox_config: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    mcp_server: Mapped[Optional["MCPServer"]] = relationship("MCPServer", back_populates="tools")
    permissions: Mapped[list["ToolPermission"]] = relationship("ToolPermission", back_populates="tool", cascade="all, delete-orphan")
    calls: Mapped[list["ToolCall"]] = relationship("ToolCall", back_populates="tool")


class MCPServer(Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (
        CheckConstraint(f"transport IN {MCP_TRANSPORTS}", name="ck_mcp_servers_transport_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    transport: Mapped[str] = mapped_column(String(50), nullable=False, default="stdio")
    command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # for stdio
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # for streamable_http / sse_legacy
    env: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # secret refs, not raw secrets
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="disconnected")
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tools: Mapped[list["ToolRegistry"]] = relationship("ToolRegistry", back_populates="mcp_server")


class ToolPermission(Base):
    __tablename__ = "tool_permissions"
    __table_args__ = (
        CheckConstraint(f"permission IN {TOOL_PERMISSIONS}", name="ck_tool_permissions_permission_valid"),
        UniqueConstraint("tool_id", "agent_type", "mission_id", name="uq_tool_permissions_tool_agent_mission"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tool_id: Mapped[str] = mapped_column(String(100), ForeignKey("tool_registry.id", ondelete="CASCADE"), nullable=False)
    agent_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # None means all agents
    mission_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("missions.id", ondelete="CASCADE"), nullable=True)
    permission: Mapped[str] = mapped_column(String(50), nullable=False)
    arg_pattern: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # e.g., {"path": "^/workspace/output/.*"}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tool: Mapped["ToolRegistry"] = relationship("ToolRegistry", back_populates="permissions")
    mission: Mapped[Optional["Mission"]] = relationship("Mission")


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(f"type IN {APPROVAL_TYPES}", name="ck_approvals_type_valid"),
        CheckConstraint(f"status IN {APPROVAL_STATUSES}", name="ck_approvals_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mission_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("missions.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    agent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=True)
    tool_call_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("tool_calls.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="tool")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    requested_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    requested_payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # action, args, reasoning, risk_level
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    edited_args: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # optional edited args
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    mission: Mapped["Mission"] = relationship("Mission")
    task: Mapped[Optional["Task"]] = relationship("Task")
    agent_run: Mapped[Optional["AgentRun"]] = relationship("AgentRun")
    tool_call: Mapped[Optional["ToolCall"]] = relationship("ToolCall", back_populates="approval", foreign_keys=[tool_call_id])


class ToolCall(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        CheckConstraint(f"status IN {TOOL_CALL_STATUSES}", name="ck_tool_calls_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=True)
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    tool_id: Mapped[str] = mapped_column(String(100), ForeignKey("tool_registry.id", ondelete="CASCADE"), nullable=False)
    args: Mapped[Any] = mapped_column(JSON, nullable=False)
    result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    permission_decision: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    agent_run: Mapped[Optional["AgentRun"]] = relationship("AgentRun")
    task: Mapped[Optional["Task"]] = relationship("Task")
    tool: Mapped["ToolRegistry"] = relationship("ToolRegistry", back_populates="calls")
    approval: Mapped[Optional["Approval"]] = relationship("Approval", back_populates="tool_call", foreign_keys=[Approval.tool_call_id])
    approval_link: Mapped[Optional["Approval"]] = relationship("Approval", foreign_keys=[approval_id], overlaps="approval,tool_call")
