"""
Mission model - Phase 2B Persistence Foundation
Reconciled with shared/src/mission.ts MissionStatus
"""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Text, DateTime, Integer, func, CheckConstraint, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

# Shared MissionStatus vocabulary - MUST match packages/shared/src/mission.ts
# Do not create second incompatible vocabulary silently
MISSION_STATUSES = (
    "draft",
    "decomposing",
    "planned",
    "running",
    "awaiting_approval",
    "paused",
    "completed",
    "failed",
    "cancelled",
    "archived",
)

MISSION_TEMPLATES = ("research", "code", "analysis", "general")


class Mission(Base):
    __tablename__ = "missions"
    __table_args__ = (
        CheckConstraint(
            f"status IN {MISSION_STATUSES}",
            name="ck_missions_status_valid",
        ),
        CheckConstraint(
            f"template IN {MISSION_TEMPLATES}",
            name="ck_missions_template_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        # FK deferred to avoid circular import in scaffold, added via migration FK
        # For Phase 2B-1, keep nullable and no FK constraint in model, add in migration
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    template: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    dag: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    approval_policy: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    budget_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    budget_cost_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships - deferred to avoid import cycles, use string
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="mission", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship("Event", back_populates="mission", cascade="all, delete-orphan")
