from fastapi import APIRouter

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/collections")
async def list_collections():
    return {"data": [], "status": "scaffold - local-first embedding, replaceable"}
