"""
MissionState - Phase 2B-3 LangGraph State
Typed, serializable, checkpoint-friendly, no duplication of unrelated frontend types
"""

from typing import TypedDict, List, Dict, Optional, Any, Annotated
import uuid
from operator import add


class TaskState(TypedDict):
    id: str
    title: str
    description: Optional[str]
    agent_type: str
    status: str  # pending, running, completed, failed, etc.
    dependencies: List[str]
    output: Optional[Dict[str, Any]]
    error: Optional[str]
    agent_run_id: Optional[str]
    token_usage: int
    cost_cents: int


class AgentRunState(TypedDict):
    id: str
    task_id: str
    agent_id: Optional[str]
    agent_type: str
    status: str
    token_usage: int
    cost_cents: int


class MissionState(TypedDict, total=False):
    """
    Typed MissionState for LangGraph
    Includes at minimum: mission_id, goal, title, template, status, tasks, dag, agent assignments, agent runs, messages, approvals_pending, cost/token tracking, error, next_action
    Keep state serializable and checkpoint-friendly
    """

    mission_id: str
    goal: str
    title: str
    template: str
    status: str

    # Tasks and DAG
    tasks: List[TaskState]
    dag: Dict[str, Any]  # nodes, edges, layers, topological_order

    # Agent assignments
    agent_assignments: Dict[str, str]  # task_id -> agent_type
    agent_runs: List[AgentRunState]

    # Messages (for future LLM interactions, keep simple for now)
    messages: Annotated[List[Dict[str, Any]], add]

    # Approvals pending (placeholder for next phase)
    approvals_pending: List[Dict[str, Any]]

    # Cost/token tracking
    total_tokens: int
    total_cost_cents: int
    cost_breakdown: Dict[str, int]

    # Error handling
    error: Optional[str]
    error_details: Optional[Dict[str, Any]]

    # Next action for graph routing
    next_action: Optional[str]

    # Metadata
    metadata: Optional[Dict[str, Any]]

    # Execution tracking
    current_task_id: Optional[str]
    completed_tasks: List[str]
    failed_tasks: List[str]
