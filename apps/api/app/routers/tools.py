"""
Tools router - Phase 2B-4 Real Implementation with explicit scoping
GET /api/v1/tools, GET /tools/{tool_id}, GET /tool-calls/{id}
All Bearer auth, Pydantic validation, mission/user scoping, never leak secrets

Scoping Boundary:
- D4 single dev token model: dev-user owns all in MVP
- Tool registry is global but tool calls are scoped via mission ownership
- Explicit scoping via tool_call_service prevents unrestricted access when multi-user introduced
"""

from typing import Optional, List
import uuid
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.tool import ToolCall
from app.services.tool_registry import tool_registry_service
from app.services.tool_call import tool_call_service
from app.schemas.tool import ToolResponse, ToolCallResponse
from app.core.exceptions import NotFoundError, PermissionDeniedError
from sqlalchemy import select

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=dict)
async def list_tools(
    source: Optional[str] = Query(None, description="Filter by source: builtin, mcp"),
    risk_level: Optional[str] = Query(None, description="Filter by risk_level"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    tools = await tool_registry_service.list_tools(session, source=source, risk_level=risk_level)
    data = []
    for t in tools:
        data.append(
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "source": t.source,
                "mcp_server_id": str(t.mcp_server_id) if t.mcp_server_id else None,
                "input_schema": t.input_schema,
                "output_schema": t.output_schema,
                "capability_tags": t.capability_tags,
                "risk_level": t.risk_level,
                "default_permission": t.default_permission,
                "sandbox_config": t.sandbox_config,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
        )
    return {"data": data, "total": len(data)}


@router.get("/{tool_id}", response_model=dict)
async def get_tool(
    tool_id: str = Path(..., description="Tool ID"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    tool = await tool_registry_service.get_tool(session, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail={"error": {"code": "tool_not_found", "message": f"Tool {tool_id} not found"}})

    return {
        "data": {
            "id": tool.id,
            "name": tool.name,
            "description": tool.description,
            "source": tool.source,
            "mcp_server_id": str(tool.mcp_server_id) if tool.mcp_server_id else None,
            "input_schema": tool.input_schema,
            "output_schema": tool.output_schema,
            "capability_tags": tool.capability_tags,
            "risk_level": tool.risk_level,
            "default_permission": tool.default_permission,
            "sandbox_config": tool.sandbox_config,
            "created_at": tool.created_at.isoformat() if tool.created_at else None,
            "updated_at": tool.updated_at.isoformat() if tool.updated_at else None,
        }
    }


@router.get("/calls/{tool_call_id}", response_model=dict)
async def get_tool_call(
    tool_call_id: uuid.UUID = Path(..., description="Tool Call ID"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        tc = await tool_call_service.get_tool_call_scoped(session, tool_call_id, user_context=current_user)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": {"code": "tool_call_not_found", "message": str(e)}})
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail={"error": {"code": "permission_denied", "message": str(e)}})

    def redact(data):
        if not isinstance(data, dict):
            return data
        redacted = {}
        for k, v in data.items():
            if any(sk in k.lower() for sk in ["secret", "password", "token", "api_key", "credential"]):
                redacted[k] = "***REDACTED***"
            else:
                redacted[k] = v
        return redacted

    return {
        "data": {
            "id": str(tc.id),
            "agent_run_id": str(tc.agent_run_id) if tc.agent_run_id else None,
            "task_id": str(tc.task_id) if tc.task_id else None,
            "tool_id": tc.tool_id,
            "args": redact(tc.args),
            "result": redact(tc.result) if tc.result else None,
            "status": tc.status,
            "permission_decision": tc.permission_decision,
            "approval_id": str(tc.approval_id) if tc.approval_id else None,
            "latency_ms": tc.latency_ms,
            "created_at": tc.created_at.isoformat() if tc.created_at else None,
            "updated_at": tc.updated_at.isoformat() if tc.updated_at else None,
        }
    }
