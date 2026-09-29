"""
NEXUS - Models - Phase 2B Persistence Foundation + Phase 2B-4 Tool/Approval
Phase 2B-1: users, missions, tasks, task_dependencies, agents, agent_runs, events
Phase 2B-4: tool_registry, mcp_servers, tool_permissions, tool_calls, approvals

Event data model fix per review:
- events.agent_id FK -> agents.id (not agent_runs)
- events.agent_run_id nullable FK -> agent_runs.id for execution-instance attribution

Enum reconciliation:
Backend enums match shared/src exactly
"""

from app.db.base import Base
from app.models.user import User
from app.models.mission import Mission
from app.models.task import Task, TaskDependency
from app.models.agent import Agent, AgentRun
from app.models.event import Event
from app.models.tool import ToolRegistry, MCPServer, ToolPermission, ToolCall, Approval
from app.models.job import MissionJob

__all__ = [
    "Base",
    "User",
    "Mission",
    "Task",
    "TaskDependency",
    "Agent",
    "AgentRun",
    "Event",
    "ToolRegistry",
    "MCPServer",
    "ToolPermission",
    "ToolCall",
    "Approval",
    "MissionJob",
]
