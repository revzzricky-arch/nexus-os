"""phase2b persistence foundation minimal

Revision ID: 001_phase2b_persistence_foundation
Revises: 
Create Date: 2026-09-29

Minimal models per PR 2B-1:
users, missions, tasks, task_dependencies, agents, agent_runs, events
Deferred: tool_registry, mcp_servers, tool_permissions, tool_calls, approvals, audit_logs

Event data model fix:
- events.agent_id FK -> agents.id
- events.agent_run_id nullable FK -> agent_runs.id

Enum reconciliation:
MissionStatus: draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived (shared/mission.ts)
AgentState: idle, queued, planning, running, tool_calling, waiting_approval, waiting_dependency, completed, failed, cancelled (shared/agent.ts)
TaskStatus: pending, queued, running, awaiting_approval, completed, failed, cancelled, skipped (shared/task.ts)
EventType: agent_state_changed, task_status_changed, tool_call_started, tool_call_completed, tool_call_failed, message_created, approval_requested, approval_decided, mission_status_changed, mission_created, handoff, memory_created, memory_accessed, rag_queried, error, cost_updated (shared/events.ts)
EventSource: agent_runner, supervisor, tool_registry, approval_service, memory_service, system, user
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_phase2b_persistence_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgcrypto for gen_random_uuid
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # users - minimal for FK, single user MVP D4
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # missions
    op.create_table(
        "missions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("template", sa.String(length=50), nullable=False, server_default="general"),
        sa.Column("dag", postgresql.JSONB(), nullable=True),
        sa.Column("approval_policy", postgresql.JSONB(), nullable=True),
        sa.Column("budget_tokens", sa.Integer(), nullable=True),
        sa.Column("budget_cost_cents", sa.Integer(), nullable=True),
        sa.Column("cost_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'decomposing', 'planned', 'running', 'awaiting_approval', 'paused', 'completed', 'failed', 'cancelled', 'archived')",
            name="ck_missions_status_valid",
        ),
        sa.CheckConstraint(
            "template IN ('research', 'code', 'analysis', 'general')",
            name="ck_missions_template_valid",
        ),
    )
    op.create_index("ix_missions_status", "missions", ["status"])
    op.create_index("ix_missions_user_id", "missions", ["user_id"])

    # tasks
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("agent_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("token_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'awaiting_approval', 'completed', 'failed', 'cancelled', 'skipped')",
            name="ck_tasks_status_valid",
        ),
        sa.CheckConstraint(
            "agent_type IN ('supervisor', 'researcher', 'coder', 'analyst', 'custom')",
            name="ck_tasks_agent_type_valid",
        ),
    )
    op.create_index("ix_tasks_mission_id", "tasks", ["mission_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_agent_type", "tasks", ["agent_type"])

    # task_dependencies - separate table for DAG dependencies
    op.create_table(
        "task_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependencies_task_depends"),
    )
    op.create_index("ix_task_dependencies_task_id", "task_dependencies", ["task_id"])
    op.create_index("ix_task_dependencies_depends_on_task_id", "task_dependencies", ["depends_on_task_id"])

    # agents registry
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=False),
        sa.Column("system_prompt_template", sa.Text(), nullable=False),
        sa.Column("model_config", postgresql.JSONB(), nullable=False),
        sa.Column("tools", postgresql.JSONB(), nullable=True),
        sa.Column("capability_tags", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "type IN ('supervisor', 'researcher', 'coder', 'analyst', 'custom')",
            name="ck_agents_type_valid",
        ),
        sa.UniqueConstraint("type", name="uq_agents_type"),
    )

    # agent_runs - execution instances
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="idle"),
        sa.Column("state", postgresql.JSONB(), nullable=True),
        sa.Column("messages", postgresql.JSONB(), nullable=True),
        sa.Column("token_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('idle', 'queued', 'planning', 'running', 'tool_calling', 'waiting_approval', 'waiting_dependency', 'completed', 'failed', 'cancelled')",
            name="ck_agent_runs_status_valid",
        ),
    )
    op.create_index("ix_agent_runs_mission_id", "agent_runs", ["mission_id"])
    op.create_index("ix_agent_runs_task_id", "agent_runs", ["task_id"])
    op.create_index("ix_agent_runs_agent_id", "agent_runs", ["agent_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    # events - append-only, fix per review: agent_id FK -> agents.id, agent_run_id nullable FK -> agent_runs.id
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint(
            "type IN ('agent_state_changed', 'task_status_changed', 'tool_call_started', 'tool_call_completed', 'tool_call_failed', 'message_created', 'approval_requested', 'approval_decided', 'mission_status_changed', 'mission_created', 'handoff', 'memory_created', 'memory_accessed', 'rag_queried', 'error', 'cost_updated')",
            name="ck_events_type_valid",
        ),
        sa.CheckConstraint(
            "source IN ('agent_runner', 'supervisor', 'tool_registry', 'approval_service', 'memory_service', 'system', 'user')",
            name="ck_events_source_valid",
        ),
    )
    op.create_index("ix_events_mission_id", "events", ["mission_id"])
    op.create_index("ix_events_task_id", "events", ["task_id"])
    op.create_index("ix_events_agent_id", "events", ["agent_id"])
    op.create_index("ix_events_agent_run_id", "events", ["agent_run_id"])
    op.create_index("ix_events_timestamp", "events", ["timestamp"])
    op.create_index("ix_events_type", "events", ["type"])
    op.create_index("ix_events_mission_timestamp", "events", ["mission_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("agent_runs")
    op.drop_table("agents")
    op.drop_table("task_dependencies")
    op.drop_table("tasks")
    op.drop_table("missions")
    op.drop_table("users")
    # Note: keep pgcrypto extension
