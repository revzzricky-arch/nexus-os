"""
Event model - Phase 2B Persistence Foundation
Reconciled with shared/src/events.ts EventType and EventSource
Fix per review: agent_id FK -> agents.id, add nullable agent_run_id FK -> agent_runs.id
"""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, DateTime, Integer, func, CheckConstraint, ForeignKey, Index, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

# Shared vocabularies - MUST match packages/shared/src/events.ts
EVENT_TYPES = (
    "agent_state_changed",
    "task_status_changed",
    "tool_call_started",
    "tool_call_completed",
    "tool_call_failed",
    "message_created",
    "approval_requested",
    "approval_decided",
    "mission_status_changed",
    "mission_created",
    "handoff",
    "memory_created",
    "memory_accessed",
    "rag_queried",
    "error",
    "cost_updated",
)

EVENT_SOURCES = (
    "agent_runner",
    "supervisor",
    "tool_registry",
    "approval_service",
    "memory_service",
    "system",
    "user",
)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(f"type IN {EVENT_TYPES}", name="ck_events_type_valid"),
        CheckConstraint(f"source IN {EVENT_SOURCES}", name="ck_events_source_valid"),
        Index("ix_events_mission_timestamp", "mission_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Fix per review: agent_id FK -> agents.id (not agent_runs)
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Separate nullable agent_run_id FK -> agent_runs.id for execution-instance attribution
    agent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    metadata_: Mapped[Optional[Any]] = mapped_column("metadata", JSON, nullable=True)

    mission: Mapped["Mission"] = relationship("Mission", back_populates="events")
    task: Mapped[Optional["Task"]] = relationship("Task")
    agent: Mapped[Optional["Agent"]] = relationship("Agent")
    agent_run: Mapped[Optional["AgentRun"]] = relationship("AgentRun")
