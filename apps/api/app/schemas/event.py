"""
Event schemas - Phase 2B Persistence Foundation
Reconciled with shared/src/events.ts EventType and EventSource
Fix: agent_id -> agents.id, agent_run_id nullable -> agent_runs.id
"""

from typing import Optional, Any
from pydantic import BaseModel
from datetime import datetime
import uuid
from enum import Enum


class EventType(str, Enum):
    agent_state_changed = "agent_state_changed"
    task_status_changed = "task_status_changed"
    tool_call_started = "tool_call_started"
    tool_call_completed = "tool_call_completed"
    tool_call_failed = "tool_call_failed"
    message_created = "message_created"
    approval_requested = "approval_requested"
    approval_decided = "approval_decided"
    mission_status_changed = "mission_status_changed"
    mission_created = "mission_created"
    handoff = "handoff"
    memory_created = "memory_created"
    memory_accessed = "memory_accessed"
    rag_queried = "rag_queried"
    error = "error"
    cost_updated = "cost_updated"


class EventSource(str, Enum):
    agent_runner = "agent_runner"
    supervisor = "supervisor"
    tool_registry = "tool_registry"
    approval_service = "approval_service"
    memory_service = "memory_service"
    system = "system"
    user = "user"


class EventCreate(BaseModel):
    type: EventType
    source: EventSource
    mission_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None  # FK -> agents.id per correction
    agent_run_id: Optional[uuid.UUID] = None  # FK -> agent_runs.id nullable
    payload: Any
    metadata: Optional[Any] = None
    version: int = 1


class EventResponse(BaseModel):
    id: uuid.UUID
    type: EventType
    source: EventSource
    mission_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None
    agent_run_id: Optional[uuid.UUID] = None
    timestamp: datetime
    version: int = 1
    payload: Any
    metadata: Optional[Any] = None

    class Config:
        from_attributes = True


class EventEnvelope(BaseModel):
    """
    Standardized envelope matching shared/src/events.ts EventEnvelope
    Suitable for future Redis event bus and WebSocket streaming
    """

    id: uuid.UUID
    type: EventType
    source: EventSource
    mission_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None
    agent_run_id: Optional[uuid.UUID] = None
    timestamp: datetime
    version: int = 1
    payload: Any
    metadata: Optional[dict] = None
