"""
Tool schemas - Phase 2B-4 ToolRegistry + SandboxService + Permission + Approval
"""

from typing import Optional, Any, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from enum import Enum


class ToolSource(str, Enum):
    builtin = "builtin"
    mcp = "mcp"


class ToolRiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ToolPermissionType(str, Enum):
    forbidden = "forbidden"
    approval_required = "approval_required"
    auto = "auto"
    read_only_auto = "read_only_auto"


class MCPTransport(str, Enum):
    stdio = "stdio"
    streamable_http = "streamable_http"
    sse_legacy = "sse_legacy"


class ToolCallStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    denied = "denied"


class ApprovalType(str, Enum):
    tool = "tool"
    task = "task"
    mission = "mission"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"
    expired = "expired"


# Tool Registry
class ToolDefinition(BaseModel):
    id: str = Field(..., description="e.g., web_search, read_file, shell")
    name: str
    description: str
    source: ToolSource = ToolSource.builtin
    mcp_server_id: Optional[uuid.UUID] = None
    input_schema: Dict[str, Any] = Field(..., description="JSONSchema")
    output_schema: Optional[Dict[str, Any]] = None
    capability_tags: List[str] = Field(default_factory=list)
    risk_level: ToolRiskLevel = ToolRiskLevel.low
    default_permission: ToolPermissionType = ToolPermissionType.auto
    sandbox_config: Optional[Dict[str, Any]] = None


class ToolCreate(BaseModel):
    id: str
    name: str
    description: str
    source: ToolSource = ToolSource.builtin
    mcp_server_id: Optional[uuid.UUID] = None
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    capability_tags: List[str] = Field(default_factory=list)
    risk_level: ToolRiskLevel = ToolRiskLevel.low
    default_permission: ToolPermissionType = ToolPermissionType.auto
    sandbox_config: Optional[Dict[str, Any]] = None


class ToolResponse(BaseModel):
    id: str
    name: str
    description: str
    source: ToolSource
    mcp_server_id: Optional[uuid.UUID] = None
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    capability_tags: Optional[List[str]] = None
    risk_level: ToolRiskLevel
    default_permission: ToolPermissionType
    sandbox_config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# MCP Servers
class MCPServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    transport: MCPTransport = MCPTransport.stdio
    command: Optional[str] = None
    url: Optional[str] = None
    env: Optional[Dict[str, Any]] = None
    enabled: bool = True


class MCPServerUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    status: Optional[str] = None


class MCPServerResponse(BaseModel):
    id: uuid.UUID
    name: str
    transport: MCPTransport
    command: Optional[str] = None
    url: Optional[str] = None
    env: Optional[Dict[str, Any]] = None
    enabled: bool
    status: str
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Tool Permissions
class ToolPermissionCreate(BaseModel):
    tool_id: str
    agent_type: Optional[str] = None
    mission_id: Optional[uuid.UUID] = None
    permission: ToolPermissionType
    arg_pattern: Optional[Dict[str, Any]] = None


class ToolPermissionResponse(BaseModel):
    id: uuid.UUID
    tool_id: str
    agent_type: Optional[str] = None
    mission_id: Optional[uuid.UUID] = None
    permission: ToolPermissionType
    arg_pattern: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PermissionDecision(BaseModel):
    decision: str = Field(..., description="allow, deny, require_approval")
    permission: ToolPermissionType
    reason: str
    risk_level: ToolRiskLevel
    evaluated_policy: Dict[str, Any]
    requires_approval: bool = False


# Tool Calls
class ToolCallCreate(BaseModel):
    task_id: Optional[uuid.UUID] = None
    agent_run_id: Optional[uuid.UUID] = None
    tool_id: str
    args: Dict[str, Any]


class ToolCallResponse(BaseModel):
    id: uuid.UUID
    agent_run_id: Optional[uuid.UUID] = None
    task_id: Optional[uuid.UUID] = None
    tool_id: str
    args: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    status: ToolCallStatus
    permission_decision: Optional[Dict[str, Any]] = None
    approval_id: Optional[uuid.UUID] = None
    latency_ms: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Approvals
class ApprovalCreate(BaseModel):
    mission_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    agent_run_id: Optional[uuid.UUID] = None
    tool_call_id: Optional[uuid.UUID] = None
    type: ApprovalType = ApprovalType.tool
    requested_by: Optional[str] = None
    requested_payload: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="approved or denied")
    review_comment: Optional[str] = None
    edited_args: Optional[Dict[str, Any]] = None
    reviewed_by: Optional[uuid.UUID] = None


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    agent_run_id: Optional[uuid.UUID] = None
    tool_call_id: Optional[uuid.UUID] = None
    type: ApprovalType
    status: ApprovalStatus
    requested_by: Optional[str] = None
    requested_payload: Optional[Dict[str, Any]] = None
    reviewed_by: Optional[uuid.UUID] = None
    review_comment: Optional[str] = None
    edited_args: Optional[Dict[str, Any]] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True
