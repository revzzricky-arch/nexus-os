"""phase2b tool approval policy - tool_registry, mcp_servers, tool_permissions, tool_calls, approvals

Revision ID: 002_phase2b_tool_approval_policy
Revises: 001_phase2b_persistence_foundation
Create Date: 2026-09-29

Phase 2B-4: ToolRegistry + SandboxService + Permission + Approval Foundation
Creates only: tool_registry, mcp_servers, tool_permissions, tool_calls, approvals
Reuses existing Phase 2B-1 models: users, missions, tasks, task_dependencies, agents, agent_runs, events
Preserves FK integrity

Security: No dangerous execution, tool registry is source of truth
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002_phase2b_tool_approval_policy"
down_revision: Union[str, None] = "001_phase2b_persistence_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # mcp_servers - must be created first for FK from tool_registry
    op.create_table(
        "mcp_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("transport", sa.String(length=50), nullable=False, server_default="stdio"),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("env", postgresql.JSONB(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="disconnected"),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "transport IN ('stdio', 'streamable_http', 'sse_legacy')",
            name="ck_mcp_servers_transport_valid",
        ),
    )

    # tool_registry
    op.create_table(
        "tool_registry",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="builtin"),
        sa.Column("mcp_server_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("input_schema", postgresql.JSONB(), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(), nullable=True),
        sa.Column("capability_tags", postgresql.JSONB(), nullable=True),
        sa.Column("risk_level", sa.String(length=50), nullable=False, server_default="low"),
        sa.Column("default_permission", sa.String(length=50), nullable=False, server_default="auto"),
        sa.Column("sandbox_config", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source IN ('builtin', 'mcp')", name="ck_tool_registry_source_valid"),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high', 'critical')", name="ck_tool_registry_risk_valid"),
        sa.CheckConstraint("default_permission IN ('forbidden', 'approval_required', 'auto', 'read_only_auto')", name="ck_tool_registry_permission_valid"),
    )
    op.create_index("ix_tool_registry_mcp_server_id", "tool_registry", ["mcp_server_id"])
    op.create_index("ix_tool_registry_source", "tool_registry", ["source"])
    op.create_index("ix_tool_registry_risk_level", "tool_registry", ["risk_level"])

    # approvals - create before tool_calls because tool_calls has FK to approvals
    # But approvals also has FK to tool_calls (tool_call_id) SET NULL, so order matters - create approvals first without tool_calls FK, then add tool_calls, then approvals already has tool_call_id FK to tool_calls which will be added as separate? 
    # To avoid circular, we create approvals with tool_call_id FK that references tool_calls which doesn't exist yet, so we need to create approvals without that FK first, then add it later, or create both with deferred.
    # Simpler: create approvals with tool_call_id nullable and no FK constraint initially, then add FK after tool_calls creation via separate op? 
    # For Alembic, we can create approvals with FK to tool_calls that will exist after tool_calls table creation if we create tool_calls first without approval_id FK, then approvals with tool_call_id FK, then add approval_id FK to tool_calls via alter.
    # Let's create approvals first without tool_call_id FK, then tool_calls, then add FKs via alter? Simpler: create both tables without circular FKs, then add FKs.
    # Approach: Create approvals without tool_call_id FK, create tool_calls without approval_id FK, then add FKs via create_foreign_key
    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("tool_call_id", postgresql.UUID(as_uuid=True), nullable=True),  # FK added later
        sa.Column("type", sa.String(length=50), nullable=False, server_default="tool"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(length=255), nullable=True),
        sa.Column("requested_payload", postgresql.JSONB(), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("edited_args", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('tool', 'task', 'mission')", name="ck_approvals_type_valid"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'denied', 'expired')", name="ck_approvals_status_valid"),
    )
    op.create_index("ix_approvals_mission_id", "approvals", ["mission_id"])
    op.create_index("ix_approvals_task_id", "approvals", ["task_id"])
    op.create_index("ix_approvals_agent_run_id", "approvals", ["agent_run_id"])
    op.create_index("ix_approvals_status", "approvals", ["status"])
    op.create_index("ix_approvals_tool_call_id", "approvals", ["tool_call_id"])

    # tool_permissions
    op.create_table(
        "tool_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tool_id", sa.String(length=100), sa.ForeignKey("tool_registry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_type", sa.String(length=50), nullable=True),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("permission", sa.String(length=50), nullable=False),
        sa.Column("arg_pattern", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("permission IN ('forbidden', 'approval_required', 'auto', 'read_only_auto')", name="ck_tool_permissions_permission_valid"),
        sa.UniqueConstraint("tool_id", "agent_type", "mission_id", name="uq_tool_permissions_tool_agent_mission"),
    )
    op.create_index("ix_tool_permissions_tool_id", "tool_permissions", ["tool_id"])
    op.create_index("ix_tool_permissions_agent_type", "tool_permissions", ["agent_type"])
    op.create_index("ix_tool_permissions_mission_id", "tool_permissions", ["mission_id"])

    # tool_calls
    op.create_table(
        "tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("tool_id", sa.String(length=100), sa.ForeignKey("tool_registry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("args", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("permission_decision", postgresql.JSONB(), nullable=True),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),  # FK added later
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'running', 'success', 'failed', 'denied')", name="ck_tool_calls_status_valid"),
    )
    op.create_index("ix_tool_calls_agent_run_id", "tool_calls", ["agent_run_id"])
    op.create_index("ix_tool_calls_task_id", "tool_calls", ["task_id"])
    op.create_index("ix_tool_calls_tool_id", "tool_calls", ["tool_id"])
    op.create_index("ix_tool_calls_status", "tool_calls", ["status"])

    # Now add circular FKs
    op.create_foreign_key(
        "fk_approvals_tool_call_id_tool_calls",
        "approvals",
        "tool_calls",
        ["tool_call_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_tool_calls_approval_id_approvals",
        "tool_calls",
        "approvals",
        ["approval_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tool_calls_approval_id", "tool_calls", ["approval_id"])


def downgrade() -> None:
    op.drop_constraint("fk_tool_calls_approval_id_approvals", "tool_calls", type_="foreignkey")
    op.drop_constraint("fk_approvals_tool_call_id_tool_calls", "approvals", type_="foreignkey")
    op.drop_table("tool_calls")
    op.drop_table("tool_permissions")
    op.drop_table("approvals")
    op.drop_table("tool_registry")
    op.drop_table("mcp_servers")
