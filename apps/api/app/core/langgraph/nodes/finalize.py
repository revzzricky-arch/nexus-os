"""
Finalize Node - Phase 2B-3
Finalizes mission, determines completed/failed, emits final events via state
"""

from typing import Dict, Any

from app.core.langgraph.state import MissionState


async def finalize_node(state: MissionState) -> Dict[str, Any]:
    """
    Finalize mission execution
    Input: tasks, completed_tasks, failed_tasks, error
    Output: status=completed or failed, next_action=None
    """
    error = state.get("error")
    failed_tasks = state.get("failed_tasks", [])
    completed_tasks = state.get("completed_tasks", [])

    try:
        if error or failed_tasks:
            # Failure path
            return {
                "status": "failed",
                "next_action": None,
                "messages": [{"role": "system", "content": f"Mission failed: {error or f'{len(failed_tasks)} tasks failed'}"}],
            }
        else:
            # Success path
            return {
                "status": "completed",
                "next_action": None,
                "messages": [{"role": "system", "content": f"Mission completed: {len(completed_tasks)} tasks"}],
            }

    except Exception as e:
        return {
            "error": str(e),
            "error_details": {"node": "finalize", "exception": str(e)[:500]},
            "status": "failed",
            "next_action": None,
        }
