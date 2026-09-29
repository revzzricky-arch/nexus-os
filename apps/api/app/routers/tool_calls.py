"""
Tool Calls router - Phase 2B-4
GET /api/v1/tool-calls/{id}
"""

import uuid
from fastapi import APIRouter, Depends, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.tool import ToolCall

router = APIRouter(prefix="/tool-calls", tags=["tool-calls"])


@router.get("/{tool_call_id}", response_model=dict)
async def get_tool_call(
    tool_call_id: uuid.UUID = Path(..., description="Tool Call ID"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(select(ToolCall).where(ToolCall.id == tool_call_id))
    tc = result.scalar_one_or_none()
    if not tc:
        raise HTTPException(status_code=404, detail={"error": {"code": "tool_call_not_found", "message": f"Tool call {tool_call_id} not found"}})

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
