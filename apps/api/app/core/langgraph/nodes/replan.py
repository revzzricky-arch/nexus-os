"""
Replan Node - Placeholder for next phase
"""

from typing import Dict, Any

from app.core.langgraph.state import MissionState


async def replan_node(state: MissionState) -> Dict[str, Any]:
    """
    Placeholder - replans mission on failure, will be implemented later
    For Phase 2B-3, simply passes through to finalize
    """
    return {
        "next_action": "finalize",
        "messages": [{"role": "system", "content": "Replan placeholder - not implemented in Phase 2B-3"}],
    }
