"""
Mission schemas - Phase 2B Persistence Foundation
Reconciled with shared/src/mission.ts
MissionStatus: draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived
"""

from typing import Optional, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from enum import Enum


class MissionStatus(str, Enum):
    draft = "draft"
    decomposing = "decomposing"
    planned = "planned"
    running = "running"
    awaiting_approval = "awaiting_approval"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    archived = "archived"


class MissionTemplate(str, Enum):
    research = "research"
    code = "code"
    analysis = "analysis"
    general = "general"


class MissionDAG(BaseModel):
    nodes: List[uuid.UUID] = []
    edges: List[dict] = []  # {from, to}
    layers: Optional[dict] = None


class ApprovalPolicy(BaseModel):
    tools: dict = Field(default_factory=dict)
    tasks: List[str] = Field(default_factory=list)
    mission_plan: bool = False
    shell_always_approval: bool = True


class MissionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    goal: str = Field(..., min_length=1)
    template: MissionTemplate = MissionTemplate.general
    approval_policy: Optional[ApprovalPolicy] = None
    budget_tokens: Optional[int] = None
    budget_cost_cents: Optional[int] = None


class MissionUpdate(BaseModel):
    status: Optional[MissionStatus] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)


class MissionResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    title: str
    goal: str
    status: MissionStatus
    template: MissionTemplate
    dag: Optional[Any] = None
    approval_policy: Optional[Any] = None
    budget_tokens: Optional[int] = None
    budget_cost_cents: Optional[int] = None
    cost_tokens: int = 0
    cost_cents: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MissionPlanTask(BaseModel):
    title: str
    description: Optional[str] = None
    agent_type: str
    dependencies: List[str] = Field(default_factory=list)
    input: Optional[dict] = None


class MissionPlan(BaseModel):
    """
    Typed execution plan suitable for LangGraph - supervisor output
    Provider-independent, validated via Pydantic
    """

    tasks: List[MissionPlanTask]
    dag: Optional[MissionDAG] = None
