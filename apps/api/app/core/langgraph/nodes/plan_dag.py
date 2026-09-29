"""
Plan DAG Node - Phase 2B-3
Validates DAG, computes layers, topological order, deterministic ordering
"""

from typing import Dict, Any

from app.core.langgraph.state import MissionState
from app.core.dag import validate_and_plan_dag, DAGValidationError
from app.services.supervisor import supervisor_service


async def plan_dag_node(state: MissionState) -> Dict[str, Any]:
    """
    Plan and validate DAG from tasks
    Input: tasks
    Output: dag with nodes, edges, layers, topological_order, status=planned
    """
    tasks = state.get("tasks", [])

    try:
        # Convert tasks to DAG format
        dag_tasks = [
            {"id": t["id"], "title": t["title"], "dependencies": t.get("dependencies", [])}
            for t in tasks
        ]

        result = validate_and_plan_dag(dag_tasks)

        dag = {
            "nodes": result.nodes,
            "edges": result.edges,
            "layers": result.layers,
            "topological_order": result.topological_order,
        }

        return {
            "dag": dag,
            "status": "planned",
            "next_action": "assign",
            "messages": [{"role": "system", "content": f"Planned DAG with {len(result.nodes)} nodes, {len(result.edges)} edges"}],
        }

    except DAGValidationError as e:
        return {
            "error": e.message,
            "error_details": {"node": "plan_dag", "details": e.details},
            "status": "failed",
            "next_action": "finalize",
        }
    except Exception as e:
        return {
            "error": str(e),
            "error_details": {"node": "plan_dag", "exception": str(e)[:500]},
            "status": "failed",
            "next_action": "finalize",
        }
