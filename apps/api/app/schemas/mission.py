"""
Mission schemas - Phase 2B Persistence Foundation + Phase 2B-3 Supervisor
Reconciled with shared/src/mission.ts
MissionStatus: draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived
"""

from typing import Optional, Any, List, Dict
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
    nodes: List[Any] = []  # Can be UUID or string for plan phase
    edges: List[dict] = []  # {from, to}
    layers: Optional[dict] = None
    topological_order: Optional[List[Any]] = None


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
    id: Optional[str] = None  # temp id for DAG planning, or real UUID after persistence
    title: str
    description: Optional[str] = None
    agent_type: str = Field(..., description="supervisor, researcher, coder, analyst, custom")
    dependencies: List[str] = Field(default_factory=list, description="List of task ids this depends on")
    input: Optional[dict] = None
    metadata: Optional[Dict[str, Any]] = None


class MissionPlan(BaseModel):
    """
    Typed execution plan suitable for LangGraph - supervisor output
    Provider-independent, validated via Pydantic
    Contains mission_id, tasks, dependencies, agent_type, descriptions, metadata for DAG creation
    """

    mission_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    goal: Optional[str] = None
    template: Optional[MissionTemplate] = None
    tasks: List[MissionPlanTask]
    dag: Optional[MissionDAG] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dag_tasks(self) -> List[Dict]:
        """Convert to format needed for DAG validation"""
        result = []
        for t in self.tasks:
            tid = t.id or t.title.lower().replace(" ", "_")
            result.append(
                {
                    "id": tid,
                    "title": t.title,
                    "dependencies": t.dependencies,
                }
            )
        return result
