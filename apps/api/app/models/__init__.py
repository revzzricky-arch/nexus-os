"""
NEXUS - Models - Phase 2B Persistence Foundation
Only minimal models per PR 2B-1 requirements:
users, missions, tasks, task_dependencies, agents, agent_runs, events
Deferred: tool_registry, mcp_servers, tool_permissions, tool_calls, approvals, audit_logs

Event data model fix per review:
- events.agent_id FK -> agents.id (not agent_runs)
- events.agent_run_id nullable FK -> agent_runs.id for execution-instance attribution

Enum reconciliation:
Backend enums match shared/src exactly (see docs/architecture.md and ADR).
MissionStatus: draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived (shared/mission.ts)
AgentState: idle, queued, planning, running, tool_calling, waiting_approval, waiting_dependency, completed, failed, cancelled (shared/agent.ts)
TaskStatus: pending, queued, running, awaiting_approval, completed, failed, cancelled, skipped (shared/task.ts)
EventType: agent_state_changed, task_status_changed, tool_call_started, tool_call_completed, tool_call_failed, message_created, approval_requested, approval_decided, mission_status_changed, mission_created, handoff, memory_created, memory_accessed, rag_queried, error, cost_updated (shared/events.ts)
EventSource: agent_runner, supervisor, tool_registry, approval_service, memory_service, system, user
"""

from app.db.base import Base
from app.models.user import User
from app.models.mission import Mission
from app.models.task import Task, TaskDependency
from app.models.agent import Agent, AgentRun
from app.models.event import Event

__all__ = [
    "Base",
    "User",
    "Mission",
    "Task",
    "TaskDependency",
    "Agent",
    "AgentRun",
    "Event",
]
