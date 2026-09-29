from fastapi import APIRouter

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/")
async def list_memory():
    return {"data": [], "status": "scaffold - no real memory yet"}
