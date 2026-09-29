"""
LangGraph Tests - Phase 2B-3
Graph creation, state transitions, decompose→plan_dag→assign→execute_task→finalize, failure path, deterministic execution
"""

import pytest
import uuid

from app.core.langgraph.state import MissionState
from app.core.langgraph.graph import create_mission_graph, get_mission_graph, get_mission_graph_with_memory_checkpointer
from app.core.langgraph.nodes import (
    decompose_node,
    plan_dag_node,
    assign_node,
    execute_task_node,
    finalize_node,
)


@pytest.mark.asyncio
async def test_graph_creation():
    graph = get_mission_graph()
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_with_memory_checkpointer():
    graph = get_mission_graph_with_memory_checkpointer()
    assert graph is not None


@pytest.mark.asyncio
async def test_decompose_node():
    state: MissionState = {
        "mission_id": str(uuid.uuid4()),
        "goal": "Research AI trends",
        "title": "AI Research",
        "template": "research",
        "status": "draft",
        "tasks": [],
        "dag": {},
        "agent_assignments": {},
        "agent_runs": [],
        "messages": [],
        "approvals_pending": [],
        "total_tokens": 0,
        "total_cost_cents": 0,
        "cost_breakdown": {},
        "error": None,
        "error_details": None,
        "next_action": None,
        "metadata": {},
        "current_task_id": None,
        "completed_tasks": [],
        "failed_tasks": [],
    }

    result = await decompose_node(state)

    assert "tasks" in result
    assert len(result["tasks"]) >= 2
    assert result["status"] == "decomposing"
    assert result["next_action"] == "plan_dag"
    # Should not have error for valid input
    assert result.get("error") is None


@pytest.mark.asyncio
async def test_plan_dag_node():
    state: MissionState = {
        "mission_id": str(uuid.uuid4()),
        "goal": "Test",
        "title": "Test",
        "template": "general",
        "status": "decomposing",
        "tasks": [
            {"id": "task_1", "title": "Task 1", "description": "First", "agent_type": "researcher", "status": "pending", "dependencies": [], "output": None, "error": None, "agent_run_id": None, "token_usage": 0, "cost_cents": 0},
            {"id": "task_2", "title": "Task 2", "description": "Second", "agent_type": "coder", "status": "pending", "dependencies": ["task_1"], "output": None, "error": None, "agent_run_id": None, "token_usage": 0, "cost_cents": 0},
        ],
        "dag": {},
        "agent_assignments": {},
        "agent_runs": [],
        "messages": [],
        "approvals_pending": [],
        "total_tokens": 0,
        "total_cost_cents": 0,
        "cost_breakdown": {},
        "error": None,
        "error_details": None,
        "next_action": None,
        "metadata": {},
        "current_task_id": None,
        "completed_tasks": [],
        "failed_tasks": [],
    }

    result = await plan_dag_node(state)

    assert "dag" in result
    assert result["status"] == "planned"
    assert result["next_action"] == "assign"
    assert len(result["dag"]["nodes"]) == 2
    assert len(result["dag"]["edges"]) == 1


@pytest.mark.asyncio
async def test_assign_node():
    state: MissionState = {
        "mission_id": str(uuid.uuid4()),
        "goal": "Test",
        "title": "Test",
        "template": "general",
        "status": "planned",
        "tasks": [
            {"id": "research_task", "title": "Research Objective", "description": "Gather info", "agent_type": "researcher", "status": "pending", "dependencies": [], "output": None, "error": None, "agent_run_id": None, "token_usage": 0, "cost_cents": 0},
            {"id": "code_task", "title": "Implement Code", "description": "Write code", "agent_type": "coder", "status": "pending", "dependencies": ["research_task"], "output": None, "error": None, "agent_run_id": None, "token_usage": 0, "cost_cents": 0},
        ],
        "dag": {"nodes": ["research_task", "code_task"], "edges": [{"from": "research_task", "to": "code_task"}], "layers": {"research_task": 0, "code_task": 1}, "topological_order": ["research_task", "code_task"]},
        "agent_assignments": {},
        "agent_runs": [],
        "messages": [],
        "approvals_pending": [],
        "total_tokens": 0,
        "total_cost_cents": 0,
        "cost_breakdown": {},
        "error": None,
        "error_details": None,
        "next_action": None,
        "metadata": {},
        "current_task_id": None,
        "completed_tasks": [],
        "failed_tasks": [],
    }

    result = await assign_node(state)

    assert "agent_assignments" in result
    assert len(result["agent_assignments"]) == 2
    assert result["agent_assignments"]["research_task"] == "researcher"
    assert result["agent_assignments"]["code_task"] == "coder"
    assert result["next_action"] == "execute_task"


@pytest.mark.asyncio
async def test_execute_task_node():
    state: MissionState = {
        "mission_id": str(uuid.uuid4()),
        "goal": "Test",
        "title": "Test",
        "template": "general",
        "status": "planned",
        "tasks": [
            {"id": "task_1", "title": "Task 1", "description": "First", "agent_type": "researcher", "status": "pending", "dependencies": [], "output": None, "error": None, "agent_run_id": None, "token_usage": 0, "cost_cents": 0},
            {"id": "task_2", "title": "Task 2", "description": "Second", "agent_type": "coder", "status": "pending", "dependencies": ["task_1"], "output": None, "error": None, "agent_run_id": None, "token_usage": 0, "cost_cents": 0},
        ],
        "dag": {"nodes": ["task_1", "task_2"], "edges": [{"from": "task_1", "to": "task_2"}], "layers": {"task_1": 0, "task_2": 1}, "topological_order": ["task_1", "task_2"]},
        "agent_assignments": {"task_1": "researcher", "task_2": "coder"},
        "agent_runs": [],
        "messages": [],
        "approvals_pending": [],
        "total_tokens": 0,
        "total_cost_cents": 0,
        "cost_breakdown": {},
        "error": None,
        "error_details": None,
        "next_action": None,
        "metadata": {},
        "current_task_id": None,
        "completed_tasks": [],
        "failed_tasks": [],
    }

    result = await execute_task_node(state)

    assert result["status"] == "running"
    assert result["next_action"] == "finalize"
    assert len(result["completed_tasks"]) == 2
    assert result["total_tokens"] > 0


@pytest.mark.asyncio
async def test_finalize_node_success():
    state: MissionState = {
        "mission_id": str(uuid.uuid4()),
        "goal": "Test",
        "title": "Test",
        "template": "general",
        "status": "running",
        "tasks": [],
        "dag": {},
        "agent_assignments": {},
        "agent_runs": [],
        "messages": [],
        "approvals_pending": [],
        "total_tokens": 100,
        "total_cost_cents": 10,
        "cost_breakdown": {},
        "error": None,
        "error_details": None,
        "next_action": None,
        "metadata": {},
        "current_task_id": None,
        "completed_tasks": ["task_1", "task_2"],
        "failed_tasks": [],
    }

    result = await finalize_node(state)

    assert result["status"] == "completed"
    assert result["next_action"] is None


@pytest.mark.asyncio
async def test_finalize_node_failure():
    state: MissionState = {
        "mission_id": str(uuid.uuid4()),
        "goal": "Test",
        "title": "Test",
        "template": "general",
        "status": "running",
        "tasks": [],
        "dag": {},
        "agent_assignments": {},
        "agent_runs": [],
        "messages": [],
        "approvals_pending": [],
        "total_tokens": 0,
        "total_cost_cents": 0,
        "cost_breakdown": {},
        "error": "Something failed",
        "error_details": {"reason": "test"},
        "next_action": None,
        "metadata": {},
        "current_task_id": None,
        "completed_tasks": [],
        "failed_tasks": ["task_1"],
    }

    result = await finalize_node(state)

    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_full_graph_execution():
    graph = get_mission_graph()

    initial_state: MissionState = {
        "mission_id": str(uuid.uuid4()),
        "goal": "Research AI trends and create report",
        "title": "AI Research Mission",
        "template": "research",
        "status": "draft",
        "tasks": [],
        "dag": {},
        "agent_assignments": {},
        "agent_runs": [],
        "messages": [],
        "approvals_pending": [],
        "total_tokens": 0,
        "total_cost_cents": 0,
        "cost_breakdown": {},
        "error": None,
        "error_details": None,
        "next_action": None,
        "metadata": {},
        "current_task_id": None,
        "completed_tasks": [],
        "failed_tasks": [],
    }

    # Use ainvoke to get final full state (not just last node update)
    final_state = await graph.ainvoke(initial_state)

    assert final_state is not None
    assert final_state.get("status") in ["completed", "failed"]
    # Should have gone through all nodes - tasks should exist in final state
    assert "tasks" in final_state
    assert len(final_state["tasks"]) >= 2


@pytest.mark.asyncio
async def test_graph_deterministic_execution():
    graph = get_mission_graph()

    initial_state: MissionState = {
        "mission_id": str(uuid.uuid4()),
        "goal": "Deterministic test",
        "title": "Deterministic",
        "template": "general",
        "status": "draft",
        "tasks": [],
        "dag": {},
        "agent_assignments": {},
        "agent_runs": [],
        "messages": [],
        "approvals_pending": [],
        "total_tokens": 0,
        "total_cost_cents": 0,
        "cost_breakdown": {},
        "error": None,
        "error_details": None,
        "next_action": None,
        "metadata": {},
        "current_task_id": None,
        "completed_tasks": [],
        "failed_tasks": [],
    }

    # Run twice, should be deterministic
    final_states = []
    for _ in range(2):
        final_state = await graph.ainvoke(initial_state)
        final_states.append(final_state)

    # Both runs should have same number of tasks
    assert len(final_states[0].get("tasks", [])) == len(final_states[1].get("tasks", []))
    assert final_states[0].get("status") == final_states[1].get("status")


@pytest.mark.asyncio
async def test_failure_path():
    graph = get_mission_graph()

    # Create state with invalid DAG that will cause failure in plan_dag
    initial_state: MissionState = {
        "mission_id": str(uuid.uuid4()),
        "goal": "Test failure",
        "title": "Failure Test",
        "template": "general",
        "status": "draft",
        "tasks": [
            {"id": "a", "title": "A", "description": "A", "agent_type": "researcher", "status": "pending", "dependencies": ["b"], "output": None, "error": None, "agent_run_id": None, "token_usage": 0, "cost_cents": 0},
            {"id": "b", "title": "B", "description": "B", "agent_type": "coder", "status": "pending", "dependencies": ["a"], "output": None, "error": None, "agent_run_id": None, "token_usage": 0, "cost_cents": 0},
        ],
        "dag": {},
        "agent_assignments": {},
        "agent_runs": [],
        "messages": [],
        "approvals_pending": [],
        "total_tokens": 0,
        "total_cost_cents": 0,
        "cost_breakdown": {},
        "error": None,
        "error_details": None,
        "next_action": None,
        "metadata": {},
        "current_task_id": None,
        "completed_tasks": [],
        "failed_tasks": [],
    }

    # Directly test plan_dag node with cycle
    from app.core.langgraph.nodes.plan_dag import plan_dag_node

    result = await plan_dag_node(initial_state)
    assert result["status"] == "failed"
    assert "error" in result
