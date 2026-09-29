"""
Agent schemas - Phase 2B Persistence Foundation
Reconciled with shared/src/agent.ts AgentState and AgentType
Fix: model_config field name conflicts with Pydantic v2 reserved name, use alias
"""

from typing import Optional, Any, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import uuid
from enum import Enum


class AgentType(str, Enum):
    supervisor = "supervisor"
    researcher = "researcher"
    coder = "coder"
    analyst = "analyst"
    custom = "custom"


class AgentState(str, Enum):
    idle = "idle"
    queued = "queued"
    planning = "planning"
    running = "running"
    tool_calling = "tool_calling"
    waiting_approval = "waiting_approval"
    waiting_dependency = "waiting_dependency"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AgentCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    type: AgentType
    role: str
    system_prompt_template: str
    model_configuration: dict = Field(alias="model_config")
    tools: Optional[List[str]] = None
    capability_tags: Optional[List[str]] = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, protected_namespaces=())

    id: uuid.UUID
    type: AgentType
    role: str
    system_prompt_template: str
    model_configuration: Any = Field(alias="model_config")
    tools: Optional[Any] = None
    capability_tags: Optional[Any] = None
    created_at: datetime


class AgentRunCreate(BaseModel):
    mission_id: uuid.UUID
    task_id: uuid.UUID
    agent_id: uuid.UUID
    status: AgentState = AgentState.idle


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_id: uuid.UUID
    task_id: uuid.UUID
    agent_id: uuid.UUID
    status: AgentState
    state: Optional[Any] = None
    messages: Optional[Any] = None
    token_usage: int = 0
    cost_cents: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
