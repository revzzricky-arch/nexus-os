"""
Assign Node - Phase 2B-3
Capability-based assignment using seeded agents
"""

from typing import Dict, Any

from app.core.langgraph.state import MissionState


# Capability mapping - configuration-driven, no large personalities
CAPABILITY_KEYWORDS = {
    "researcher": ["research", "gather", "collect", "find", "search", "investigate", "explore", "objective", "understand"],
    "coder": ["code", "implement", "develop", "program", "build", "create", "write", "test", "review"],
    "analyst": ["analyze", "analysis", "data", "process", "visualize", "report", "synthesize", "findings", "insights"],
    "supervisor": ["plan", "coordinate", "manage", "design", "finalize", "document", "synthesize", "understand", "goal"],
}


def _infer_agent_type(title: str, description: str, current_type: str) -> str:
    """Infer agent type from task content if not valid"""
    valid_types = ["supervisor", "researcher", "coder", "analyst", "custom"]
    if current_type in valid_types:
        return current_type

    combined = f"{title.lower()} {description.lower()}"

    scores = {}
    for agent_type, keywords in CAPABILITY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        scores[agent_type] = score

    # Return highest scoring, or supervisor as default
    if scores:
        best = max(scores, key=lambda k: scores[k])
        if scores[best] > 0:
            return best

    return "supervisor"


async def assign_node(state: MissionState) -> Dict[str, Any]:
    """
    Assign tasks to agent types based on capability
    Input: tasks
    Output: agent_assignments, status still planned, next_action=execute_task
    """
    tasks = state.get("tasks", [])

    try:
        assignments = {}

        for task in tasks:
            task_id = task["id"]
            title = task.get("title", "")
            description = task.get("description", "")
            current_type = task.get("agent_type", "supervisor")

            assigned_type = _infer_agent_type(title, description, current_type)
            assignments[task_id] = assigned_type

            # Update task with assigned type (ensure consistency)
            task["agent_type"] = assigned_type

        return {
            "agent_assignments": assignments,
            "tasks": tasks,  # updated with assigned types
            "status": "planned",
            "next_action": "execute_task",
            "messages": [{"role": "system", "content": f"Assigned {len(assignments)} tasks to agents"}],
        }

    except Exception as e:
        return {
            "error": str(e),
            "error_details": {"node": "assign", "exception": str(e)[:500]},
            "status": "failed",
            "next_action": "finalize",
        }
