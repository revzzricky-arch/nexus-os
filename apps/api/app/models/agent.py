"""
Agent registry + AgentRun - Phase 2B Persistence Foundation
Reconciled with shared/src/agent.ts AgentState and AgentType
"""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Text, DateTime, Integer, func, CheckConstraint, ForeignKey, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

# Shared vocabularies - MUST match packages/shared/src/agent.ts
AGENT_TYPES = ("supervisor", "researcher", "coder", "analyst", "custom")

AGENT_STATES = (
    "idle",
    "queued",
    "planning",
    "running",
    "tool_calling",
    "waiting_approval",
    "waiting_dependency",
    "completed",
    "failed",
    "cancelled",
)


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint(f"type IN {AGENT_TYPES}", name="ck_agents_type_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    model_config: Mapped[Any] = mapped_column(JSON, nullable=False)
    tools: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # JSON array of tool ids
    capability_tags: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="agent")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(f"status IN {AGENT_STATES}", name="ck_agent_runs_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="idle", index=True)
    state: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # LangGraph checkpoint
    messages: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    token_usage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="runs")
    mission: Mapped["Mission"] = relationship("Mission")
    task: Mapped["Task"] = relationship("Task")
