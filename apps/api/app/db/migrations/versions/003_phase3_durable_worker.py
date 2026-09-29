"""phase3 durable worker - mission_jobs table with lease/heartbeat and idempotency

Revision ID: 003_phase3_durable_worker
Revises: 002_phase2b_tool_approval_policy
Create Date: 2026-09-29

Phase 3 PR 3.1: Durable Worker + Mission Job System
- Creates mission_jobs table with fields id, mission_id, execution_id, idempotency_key, status, attempts, max_retries, payload, result, error, locked_at, heartbeat_at, locked_by, created_at, updated_at
- Statuses: pending, running, awaiting_approval, paused, completed, failed, cancelled
- Indexes: status+created_at, mission_id+status, execution_id, idempotency_key, locked_at, heartbeat_at, locked_by
- Unique (mission_id, idempotency_key) for idempotency
- Partial unique index for one active execution per mission: unique mission_id where status in active states (pending, running, awaiting_approval, paused) - prevents duplicate active executions
- Lease/heartbeat: locked_at + heartbeat_at + configurable lease timeout, not merely locked_at older than 5m

Security: No secrets in payload, mission/user scoping, no arbitrary execution
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_phase3_durable_worker"
down_revision: Union[str, None] = "002_phase2b_tool_approval_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mission_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'awaiting_approval', 'paused', 'completed', 'failed', 'cancelled')",
            name="ck_mission_jobs_status_valid",
        ),
        sa.UniqueConstraint("mission_id", "idempotency_key", name="uq_mission_jobs_mission_idempotency"),
    )

    # Indexes
    op.create_index("ix_mission_jobs_status_created", "mission_jobs", ["status", "created_at"])
    op.create_index("ix_mission_jobs_mission_status", "mission_jobs", ["mission_id", "status"])
    op.create_index("ix_mission_jobs_execution_id", "mission_jobs", ["execution_id"])
    op.create_index("ix_mission_jobs_idempotency_key", "mission_jobs", ["idempotency_key"])
    op.create_index("ix_mission_jobs_locked_at", "mission_jobs", ["locked_at"])
    op.create_index("ix_mission_jobs_heartbeat_at", "mission_jobs", ["heartbeat_at"])
    op.create_index("ix_mission_jobs_locked_by", "mission_jobs", ["locked_by"])
    op.create_index("ix_mission_jobs_mission_id", "mission_jobs", ["mission_id"])
    op.create_index("ix_mission_jobs_status", "mission_jobs", ["status"])

    # Partial unique index for one active execution per mission
    # Prevents duplicate active executions: only one job with status in active set per mission
    # This is the fallback idempotency when client does not provide Idempotency-Key
    # Active statuses: pending, running, awaiting_approval, paused
    op.execute(
        """
        CREATE UNIQUE INDEX uq_mission_jobs_one_active_per_mission
        ON mission_jobs (mission_id)
        WHERE status IN ('pending', 'running', 'awaiting_approval', 'paused')
        """
    )

    # Index for lease recovery: find jobs where heartbeat expired
    op.execute(
        """
        CREATE INDEX ix_mission_jobs_heartbeat_expired
        ON mission_jobs (heartbeat_at)
        WHERE status IN ('running', 'awaiting_approval', 'paused')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_mission_jobs_heartbeat_expired", table_name="mission_jobs")
    op.drop_index("uq_mission_jobs_one_active_per_mission", table_name="mission_jobs")
    op.drop_index("ix_mission_jobs_status", table_name="mission_jobs")
    op.drop_index("ix_mission_jobs_mission_id", table_name="mission_jobs")
    op.drop_index("ix_mission_jobs_locked_by", table_name="mission_jobs")
    op.drop_index("ix_mission_jobs_heartbeat_at", table_name="mission_jobs")
    op.drop_index("ix_mission_jobs_locked_at", table_name="mission_jobs")
    op.drop_index("ix_mission_jobs_idempotency_key", table_name="mission_jobs")
    op.drop_index("ix_mission_jobs_execution_id", table_name="mission_jobs")
    op.drop_index("ix_mission_jobs_mission_status", table_name="mission_jobs")
    op.drop_index("ix_mission_jobs_status_created", table_name="mission_jobs")
    op.drop_table("mission_jobs")
