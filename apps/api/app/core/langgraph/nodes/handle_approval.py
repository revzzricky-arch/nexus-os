"""
Handle Approval Node - Placeholder for next phase (tool/approval)
"""

from typing import Dict, Any

from app.core.langgraph.state import MissionState


async def handle_approval_node(state: MissionState) -> Dict[str, Any]:
    """
    Placeholder - handles approval requests, will be implemented in approval phase
    For Phase 2B-3, simply passes through
    """
    return {
        "next_action": "execute_task",
        "messages": [{"role": "system", "content": "Handle approval placeholder - not implemented in Phase 2B-3"}],
    }
