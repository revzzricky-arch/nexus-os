from fastapi import APIRouter
from app.services.mcp_manager import mcp_manager_service

router = APIRouter(prefix="/mcp-servers", tags=["mcp"])


@router.get("/")
async def list_mcp_servers():
    servers = await mcp_manager_service.list_servers()
    return {"data": servers, "status": "scaffold - stdio local + streamable_http remote, sse_legacy only"}
