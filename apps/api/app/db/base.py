"""
NEXUS - DB Base - Phase 2B Persistence Foundation
SQLAlchemy 2 async declarative base
Only minimal models: users, missions, tasks, task_dependencies, agents, agent_runs, events
Deferred: tool_registry, mcp_servers, tool_permissions, tool_calls, approvals, audit_logs
"""

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

# Naming convention for Alembic
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    metadata = metadata
