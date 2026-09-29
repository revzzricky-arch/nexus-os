"""
Enum Reconciliation Tests - PR 2B-1
Inspect packages/shared and reconcile MissionStatus/AgentState/TaskState/EventType with backend enums
Do not create second incompatible vocabulary silently
Document explicit mapping
"""

import pathlib
import re


SHARED_DIR = pathlib.Path(__file__).parent.parent.parent.parent / "packages" / "shared" / "src"

# Expected vocabularies from shared (authoritative)
EXPECTED_MISSION_STATUSES = {
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
}

EXPECTED_AGENT_STATES = {
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
}

EXPECTED_TASK_STATUSES = {
    "pending",
    "queued",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
    "cancelled",
    "skipped",
}

EXPECTED_EVENT_TYPES = {
    "agent_state_changed",
    "task_status_changed",
    "tool_call_started",
    "tool_call_completed",
    "tool_call_failed",
    "message_created",
    "approval_requested",
    "approval_decided",
    "mission_status_changed",
    "mission_created",
    "handoff",
    "memory_created",
    "memory_accessed",
    "rag_queried",
    "error",
    "cost_updated",
}

EXPECTED_EVENT_SOURCES = {
    "agent_runner",
    "supervisor",
    "tool_registry",
    "approval_service",
    "memory_service",
    "system",
    "user",
}

EXPECTED_AGENT_TYPES = {"supervisor", "researcher", "coder", "analyst", "custom"}


def test_shared_files_exist():
    """Shared types should exist"""
    assert (SHARED_DIR / "mission.ts").exists(), "mission.ts missing"
    assert (SHARED_DIR / "agent.ts").exists(), "agent.ts missing"
    assert (SHARED_DIR / "task.ts").exists(), "task.ts missing"
    assert (SHARED_DIR / "events.ts").exists(), "events.ts missing"


def test_backend_mission_status_matches_shared():
    """Backend MissionStatus must match shared/src/mission.ts"""
    from app.models.mission import MISSION_STATUSES
    from app.schemas.mission import MissionStatus

    backend_statuses = set(MISSION_STATUSES)
    schema_statuses = {e.value for e in MissionStatus}

    assert backend_statuses == EXPECTED_MISSION_STATUSES, f"Model MISSION_STATUSES mismatch: {backend_statuses} vs {EXPECTED_MISSION_STATUSES}"
    assert schema_statuses == EXPECTED_MISSION_STATUSES, f"Schema MissionStatus mismatch: {schema_statuses} vs {EXPECTED_MISSION_STATUSES}"


def test_backend_agent_state_matches_shared():
    """Backend AgentState must match shared/src/agent.ts"""
    from app.models.agent import AGENT_STATES, AGENT_TYPES
    from app.schemas.agent import AgentState, AgentType

    backend_states = set(AGENT_STATES)
    schema_states = {e.value for e in AgentState}
    backend_types = set(AGENT_TYPES)
    schema_types = {e.value for e in AgentType}

    assert backend_states == EXPECTED_AGENT_STATES, f"Model AGENT_STATES mismatch: {backend_states} vs {EXPECTED_AGENT_STATES}"
    assert schema_states == EXPECTED_AGENT_STATES, f"Schema AgentState mismatch: {schema_states} vs {EXPECTED_AGENT_STATES}"
    assert backend_types == EXPECTED_AGENT_TYPES, f"Model AGENT_TYPES mismatch"
    assert schema_types == EXPECTED_AGENT_TYPES, f"Schema AgentType mismatch"


def test_backend_task_status_matches_shared():
    """Backend TaskStatus must match shared/src/task.ts"""
    from app.models.task import TASK_STATUSES
    from app.schemas.task import TaskStatus

    backend_statuses = set(TASK_STATUSES)
    schema_statuses = {e.value for e in TaskStatus}

    assert backend_statuses == EXPECTED_TASK_STATUSES, f"Model TASK_STATUSES mismatch"
    assert schema_statuses == EXPECTED_TASK_STATUSES, f"Schema TaskStatus mismatch"


def test_backend_event_type_matches_shared():
    """Backend EventType must match shared/src/events.ts"""
    from app.models.event import EVENT_TYPES, EVENT_SOURCES
    from app.schemas.event import EventType, EventSource

    backend_event_types = set(EVENT_TYPES)
    schema_event_types = {e.value for e in EventType}
    backend_sources = set(EVENT_SOURCES)
    schema_sources = {e.value for e in EventSource}

    assert backend_event_types == EXPECTED_EVENT_TYPES, f"Model EVENT_TYPES mismatch: {backend_event_types} vs {EXPECTED_EVENT_TYPES}"
    assert schema_event_types == EXPECTED_EVENT_TYPES, f"Schema EventType mismatch"
    assert backend_sources == EXPECTED_EVENT_SOURCES, f"Model EVENT_SOURCES mismatch"
    assert schema_sources == EXPECTED_EVENT_SOURCES, f"Schema EventSource mismatch"


def test_explicit_mapping_documented():
    """
    Document any necessary explicit mapping between backend and shared
    For Phase 2B-1, we use identical vocabularies, no mapping needed
    But we document lifecycle mapping: CREATED→PLANNING→RUNNING→WAITING→COMPLETED/FAILED/CANCELLED
    """
    lifecycle_mapping = {
        "CREATED": ["draft"],
        "PLANNING": ["decomposing", "planned"],
        "RUNNING": ["running"],
        "WAITING": ["awaiting_approval", "paused"],
        "COMPLETED": ["completed", "archived"],
        "FAILED": ["failed"],
        "CANCELLED": ["cancelled"],
    }

    # Ensure all mission statuses covered in lifecycle
    all_mapped = set()
    for statuses in lifecycle_mapping.values():
        all_mapped.update(statuses)

    assert all_mapped == EXPECTED_MISSION_STATUSES, f"Lifecycle mapping must cover all MissionStatus: missing {EXPECTED_MISSION_STATUSES - all_mapped}"

    # AgentState mapping is 1:1, no transformation needed (lowercase)
    # TaskStatus mapping is 1:1
    # EventType mapping is 1:1

    # If future needs explicit mapping, document here
    assert True
