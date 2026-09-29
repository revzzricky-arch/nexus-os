"""
Agent Runner Service - Scaffold Placeholder
No real agent execution yet
"""


class AgentRunnerService:
    """Scaffold placeholder for agent runner"""

    async def run_agent(self, mission_id: str, task_id: str, agent_type: str) -> dict:
        return {
            "mission_id": mission_id,
            "task_id": task_id,
            "agent_type": agent_type,
            "status": "scaffold",
            "message": "AgentRunner placeholder - no real execution yet",
        }

    async def get_agent_state(self, agent_run_id: str) -> dict:
        return {"agent_run_id": agent_run_id, "state": "idle", "status": "scaffold"}


agent_runner_service = AgentRunnerService()
