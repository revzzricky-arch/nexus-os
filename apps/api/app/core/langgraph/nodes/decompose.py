"""
Decompose Node - Phase 2B-3
Uses SupervisorService to decompose mission into MissionPlan
"""

from typing import Dict, Any
import uuid

from app.core.langgraph.state import MissionState
from app.services.supervisor import supervisor_service


async def decompose_node(state: MissionState) -> Dict[str, Any]:
    """
    Decompose mission into tasks
    Input: mission_id, goal, template, title
    Output: tasks, dag, status=decomposing
    """
    mission_id_str = state.get("mission_id")
    goal = state.get("goal", "")
    template = state.get("template", "general")
    title = state.get("title", "")

    try:
        mission_id = uuid.UUID(mission_id_str) if mission_id_str else uuid.uuid4()

        plan = await supervisor_service.decompose_mission(
            mission_id=mission_id,
            goal=goal,
            template=template,
            title=title,
        )

        # Convert plan tasks to TaskState
        tasks = []
        for t in plan.tasks:
            task_id = t.id or t.title.lower().replace(" ", "_")
            tasks.append(
                {
                    "id": task_id,
                    "title": t.title,
                    "description": t.description,
                    "agent_type": t.agent_type,
                    "status": "pending",
                    "dependencies": t.dependencies,
                    "output": None,
                    "error": None,
                    "agent_run_id": None,
                    "token_usage": 0,
                    "cost_cents": 0,
                }
            )

        dag = plan.dag.model_dump() if plan.dag else {"nodes": [], "edges": [], "layers": {}, "topological_order": []}

        return {
            "tasks": tasks,
            "dag": dag,
            "status": "decomposing",
            "next_action": "plan_dag",
            "messages": [{"role": "system", "content": f"Decomposed mission {mission_id_str} into {len(tasks)} tasks"}],
        }

    except Exception as e:
        return {
            "error": str(e),
            "error_details": {"node": "decompose", "exception": str(e)[:500]},
            "status": "failed",
            "next_action": "finalize",
        }
