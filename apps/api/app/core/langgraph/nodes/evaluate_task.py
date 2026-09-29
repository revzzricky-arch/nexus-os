"""
Evaluate Task Node - Placeholder for next phase (tool/approval)
"""

from typing import Dict, Any

from app.core.langgraph.state import MissionState


async def evaluate_task_node(state: MissionState) -> Dict[str, Any]:
    """
    Placeholder - evaluates task output, will be implemented in tool/approval phase
    For Phase 2B-3, simply passes through
    """
    return {
        "next_action": "finalize",
        "messages": [{"role": "system", "content": "Evaluate task placeholder - not implemented in Phase 2B-3"}],
    }
