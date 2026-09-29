from fastapi import APIRouter
from app.services.tool_registry import tool_registry_service

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/")
async def list_tools():
    tools = await tool_registry_service.list_tools()
    return {"data": tools, "status": "scaffold"}
