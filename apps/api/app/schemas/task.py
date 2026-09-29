"""
Task schemas - Phase 2B Persistence Foundation
Reconciled with shared/src/task.ts TaskStatus
"""

from typing import Optional, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from enum import Enum


class TaskStatus(str, Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    skipped = "skipped"


class AgentType(str, Enum):
    supervisor = "supervisor"
    researcher = "researcher"
    coder = "coder"
    analyst = "analyst"
    custom = "custom"


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    agent_type: AgentType
    dependencies: List[uuid.UUID] = Field(default_factory=list)
    input: Optional[dict] = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    title: str
    description: Optional[str] = None
    agent_type: AgentType
    status: TaskStatus
    input: Optional[Any] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    token_usage: int = 0
    cost_cents: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskDependencyCreate(BaseModel):
    task_id: uuid.UUID
    depends_on_task_id: uuid.UUID


class TaskDependencyResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    depends_on_task_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
