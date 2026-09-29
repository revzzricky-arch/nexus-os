"""
Supervisor Service - Scaffold Placeholder
No real decomposition yet
"""

from typing import Dict, Any


class SupervisorService:
    """Scaffold placeholder for supervisor agent - planner, decomposer, router"""

    async def decompose_mission(self, mission_id: str, goal: str) -> Dict[str, Any]:
        return {
            "mission_id": mission_id,
            "status": "scaffold",
            "message": "SupervisorService placeholder - no real decomposition yet",
            "tasks": [],
        }

    async def plan_dag(self, mission_id: str) -> Dict[str, Any]:
        return {"mission_id": mission_id, "dag": {"nodes": [], "edges": []}, "status": "scaffold"}

    async def assign_tasks(self, mission_id: str) -> Dict[str, Any]:
        return {"mission_id": mission_id, "assignments": [], "status": "scaffold"}


supervisor_service = SupervisorService()
