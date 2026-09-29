from fastapi import APIRouter

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task(task_id: str):
    return {"id": task_id, "status": "scaffold", "message": "Placeholder"}
