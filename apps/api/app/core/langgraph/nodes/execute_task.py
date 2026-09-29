"""
Execute Task Node - Phase 2B-3
Uses AgentRunner safe stub to execute tasks in topological order
"""

from typing import Dict, Any
import uuid

from app.core.langgraph.state import MissionState


async def execute_task_node(state: MissionState) -> Dict[str, Any]:
    """
    Execute tasks in topological order (deterministic)
    For Phase 2B-3, this node conceptually supports multiple independent tasks,
    but keeps actual execution safe and deterministic via stub.

    In real implementation, this would iterate over tasks in topological order
    and execute them via AgentRunner. For this PR, we simulate execution
    by marking tasks as completed in order, without real side effects.

    The actual DB execution happens in orchestrator service that calls AgentRunner
    with real session. This node only updates state for graph routing.

    Input: tasks, dag, agent_assignments
    Output: tasks updated, completed_tasks, status=running, next_action=finalize or error
    """
    tasks = state.get("tasks", [])
    dag = state.get("dag", {})
    topo_order = dag.get("topological_order", [t["id"] for t in tasks])

    try:
        # For graph state, simulate execution in topological order
        # Real DB execution is done in orchestrator service outside graph for testability
        completed = []
        failed = []
        total_tokens = state.get("total_tokens", 0)
        total_cost = state.get("total_cost_cents", 0)

        # Deterministic execution: iterate in topo order
        for task_id in topo_order:
            # Find task
            task = next((t for t in tasks if t["id"] == task_id), None)
            if not task:
                continue

            # Simulate deterministic execution result
            # In real orchestrator, AgentRunner would be called with DB session
            task["status"] = "completed"
            task["output"] = {
                "type": task.get("agent_type", "supervisor"),
                "summary": f"Executed {task['title']} (stub)",
                "deterministic": True,
            }
            task["token_usage"] = len(task.get("title", "")) + len(task.get("description", "") or "")
            task["cost_cents"] = 1

            completed.append(task_id)
            total_tokens += task["token_usage"]
            total_cost += task["cost_cents"]

        return {
            "tasks": tasks,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "total_tokens": total_tokens,
            "total_cost_cents": total_cost,
            "status": "running",
            "next_action": "finalize",
            "messages": [{"role": "system", "content": f"Executed {len(completed)} tasks, {len(failed)} failed"}],
        }

    except Exception as e:
        return {
            "error": str(e),
            "error_details": {"node": "execute_task", "exception": str(e)[:500]},
            "status": "failed",
            "next_action": "finalize",
        }
