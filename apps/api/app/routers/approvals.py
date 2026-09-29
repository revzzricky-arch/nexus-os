from fastapi import APIRouter

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/")
async def list_approvals():
    return {"data": [], "status": "scaffold - balanced policy, shell always approval"}
