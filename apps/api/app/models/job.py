"""
Mission Job model - Phase 3 PR 3.1 Durable Worker + Mission Job System

Implements durable PostgreSQL-backed job system for mission execution.

Fields:
- id: UUID pk
- mission_id: FK missions.id CASCADE
- execution_id: UUID - deterministic execution identifier
- idempotency_key: optional client Idempotency-Key for duplicate prevention, unique (mission_id, idempotency_key) when not null
- status: pending, running, awaiting_approval, paused, completed, failed, cancelled
- attempts: int default 0
- max_retries: int default 3
- payload: JSONB - safe payload (goal, template, etc), no secrets, validated size
- result: JSONB nullable
- error: Text nullable
- locked_at: timestamp nullable - when claimed
- heartbeat_at: timestamp nullable - periodic heartbeat renewal
- locked_by: string nullable - worker ID
- created_at, updated_at

Indexes:
- status + created_at
- mission_id + status
- worker lease fields
- unique (mission_id, idempotency_key) partial where idempotency_key is not null
- partial unique for one active execution per mission: unique where status in active states (pending, running, awaiting_approval, paused) - prevents duplicate active executions

Security:
- No secrets in payload (validated)
- No bearer token in payload/logs
- Mission/user scoping via mission_id
- No arbitrary execution
"""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Text, DateTime, Integer, func, CheckConstraint, ForeignKey, Index, Uuid, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

JOB_STATUSES = (
    "pending",
    "running",
    "awaiting_approval",
    "paused",
    "completed",
    "failed",
    "cancelled",
)

# Active statuses - only one allowed per mission at a time (enforced via partial index in migration, and application logic)
ACTIVE_JOB_STATUSES = ("pending", "running", "awaiting_approval", "paused")


class MissionJob(Base):
    __tablename__ = "mission_jobs"
    __table_args__ = (
        CheckConstraint(
            f"status IN {JOB_STATUSES}",
            name="ck_mission_jobs_status_valid",
        ),
        # Unique idempotency per mission when key provided
        UniqueConstraint("mission_id", "idempotency_key", name="uq_mission_jobs_mission_idempotency"),
        Index("ix_mission_jobs_status_created", "status", "created_at"),
        Index("ix_mission_jobs_mission_status", "mission_id", "status"),
        Index("ix_mission_jobs_execution_id", "execution_id"),
        Index("ix_mission_jobs_idempotency_key", "idempotency_key"),
        Index("ix_mission_jobs_locked_at", "locked_at"),
        Index("ix_mission_jobs_heartbeat_at", "heartbeat_at"),
        Index("ix_mission_jobs_locked_by", "locked_by"),
        # Partial unique index for one active execution per mission will be created in migration via raw SQL
        # because SQLAlchemy doesn't support partial unique via __table_args__ easily with WHERE clause
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("missions.id", ondelete="CASCADE"),
        nullable=False,
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        default=uuid.uuid4,
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )
    payload: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
    )
    result: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    locked_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
