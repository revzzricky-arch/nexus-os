"""
Task model + TaskDependency - Phase 2B Persistence Foundation
Reconciled with shared/src/task.ts TaskStatus
"""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Text, DateTime, Integer, func, CheckConstraint, ForeignKey, UniqueConstraint, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

# Shared TaskStatus vocabulary - MUST match packages/shared/src/task.ts
TASK_STATUSES = (
    "pending",
    "queued",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
    "cancelled",
    "skipped",
)

# AgentType for tasks - matches shared/src/agent.ts AgentType
AGENT_TYPES = ("supervisor", "researcher", "coder", "analyst", "custom")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(f"status IN {TASK_STATUSES}", name="ck_tasks_status_valid"),
        CheckConstraint(f"agent_type IN {AGENT_TYPES}", name="ck_tasks_agent_type_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    input: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    output: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    token_usage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    mission: Mapped["Mission"] = relationship("Mission", back_populates="tasks")
    dependencies: Mapped[list["TaskDependency"]] = relationship(
        "TaskDependency", foreign_keys="TaskDependency.task_id", back_populates="task", cascade="all, delete-orphan"
    )
    dependents: Mapped[list["TaskDependency"]] = relationship(
        "TaskDependency", foreign_keys="TaskDependency.depends_on_task_id", back_populates="depends_on_task"
    )


class TaskDependency(Base):
    """
    Separate table for DAG dependencies, not UUID[] array, for FK integrity and extensibility
    """

    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependencies_task_depends"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    task: Mapped["Task"] = relationship("Task", foreign_keys=[task_id], back_populates="dependencies")
    depends_on_task: Mapped["Task"] = relationship("Task", foreign_keys=[depends_on_task_id], back_populates="dependents")
