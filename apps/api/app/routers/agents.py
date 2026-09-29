from fastapi import APIRouter

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/")
async def list_agents():
    return {
        "data": [
            {"id": "supervisor", "type": "supervisor", "role": "Planner"},
            {"id": "researcher", "type": "researcher", "role": "Researcher"},
            {"id": "coder", "type": "coder", "role": "Coder"},
            {"id": "analyst", "type": "analyst", "role": "Analyst"},
        ],
        "status": "scaffold - placeholder agents",
    }
