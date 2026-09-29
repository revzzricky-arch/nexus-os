"""
Missions Router - Scaffold Placeholder
"""

from fastapi import APIRouter

router = APIRouter(prefix="/missions", tags=["missions"])


@router.get("/")
async def list_missions():
    return {
        "data": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
        "status": "scaffold - no real missions yet",
    }


@router.post("/")
async def create_mission(payload: dict):
    return {
        "id": "scaffold-mission-id",
        "title": payload.get("title", "Scaffold Mission"),
        "goal": payload.get("goal", ""),
        "status": "draft",
        "message": "Scaffold placeholder - no real mission creation yet",
    }


@router.get("/{mission_id}")
async def get_mission(mission_id: str):
    return {
        "id": mission_id,
        "title": "Scaffold Mission",
        "status": "draft",
        "message": "Scaffold placeholder",
    }
