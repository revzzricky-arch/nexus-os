"""
Approvals router - Phase 2B-4 Real Implementation
GET /api/v1/approvals, GET /approvals/{approval_id}, POST /approvals/{approval_id}/decision, GET /tool-calls/{id}
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.services.approval import approval_service
from app.services.agent_runner import agent_runner_service
from app.schemas.tool import ApprovalDecisionRequest
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.event import EventCreate, EventType, EventSource
from app.services.event_bus import event_bus_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=dict)
async def list_approvals(
    mission_id: Optional[uuid.UUID] = Query(None, description="Filter by mission_id"),
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, denied, expired"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    approvals, total = await approval_service.list_approvals(
        session, mission_id=mission_id, status=status, limit=limit, offset=offset
    )
    data = []
    for a in approvals:
        data.append(
            {
                "id": str(a.id),
                "mission_id": str(a.mission_id),
                "task_id": str(a.task_id) if a.task_id else None,
                "agent_run_id": str(a.agent_run_id) if a.agent_run_id else None,
                "tool_call_id": str(a.tool_call_id) if a.tool_call_id else None,
                "type": a.type,
                "status": a.status,
                "requested_by": a.requested_by,
                "requested_payload": a.requested_payload,
                "reviewed_by": str(a.reviewed_by) if a.reviewed_by else None,
                "review_comment": a.review_comment,
                "edited_args": a.edited_args,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            }
        )
    return {"data": data, "total": total, "limit": limit, "offset": offset}


@router.get("/{approval_id}", response_model=dict)
async def get_approval(
    approval_id: uuid.UUID = Path(..., description="Approval ID"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    approval = await approval_service.get_approval(session, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail={"error": {"code": "approval_not_found", "message": f"Approval {approval_id} not found"}})

    return {
        "data": {
            "id": str(approval.id),
            "mission_id": str(approval.mission_id),
            "task_id": str(approval.task_id) if approval.task_id else None,
            "agent_run_id": str(approval.agent_run_id) if approval.agent_run_id else None,
            "tool_call_id": str(approval.tool_call_id) if approval.tool_call_id else None,
            "type": approval.type,
            "status": approval.status,
            "requested_by": approval.requested_by,
            "requested_payload": approval.requested_payload,
            "reviewed_by": str(approval.reviewed_by) if approval.reviewed_by else None,
            "review_comment": approval.review_comment,
            "edited_args": approval.edited_args,
            "created_at": approval.created_at.isoformat() if approval.created_at else None,
            "reviewed_at": approval.reviewed_at.isoformat() if approval.reviewed_at else None,
            "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        }
    }


@router.post("/{approval_id}/decision", response_model=dict)
async def decide_approval(
    approval_id: uuid.UUID = Path(..., description="Approval ID"),
    body: ApprovalDecisionRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        # Decide approval - current_user is dict per D4
        # For MVP, we don't have real user id, use None or try to get from dict
        reviewed_by_id = None
        if isinstance(current_user, dict):
            # Try to parse user_id if it's UUID, otherwise None
            try:
                uid = current_user.get("user_id")
                if uid and uid != "dev-user":
                    reviewed_by_id = uuid.UUID(uid)
            except Exception:
                reviewed_by_id = None
        else:
            reviewed_by_id = getattr(current_user, "id", None)

        approval = await approval_service.decide_approval(
            session,
            approval_id=approval_id,
            decision=body.decision,
            reviewed_by=reviewed_by_id,
            review_comment=body.review_comment,
            edited_args=body.edited_args,
        )

        # Handle execution if approved - via AgentRunner
        execution_result = None
        if body.decision == "approved":
            execution_result = await agent_runner_service.handle_approval_decision(
                session, approval_id, "approved", edited_args=body.edited_args
            )
        else:
            execution_result = await agent_runner_service.handle_approval_decision(
                session, approval_id, "denied"
            )

        return {
            "data": {
                "id": str(approval.id),
                "mission_id": str(approval.mission_id),
                "status": approval.status,
                "decision": body.decision,
                "reviewed_by": str(approval.reviewed_by) if approval.reviewed_by else None,
                "review_comment": approval.review_comment,
                "edited_args": approval.edited_args,
                "reviewed_at": approval.reviewed_at.isoformat() if approval.reviewed_at else None,
                "execution_result": execution_result,
            }
        }

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": str(e)}})
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "validation_error", "message": str(e), "details": e.details}})


@router.get("/tool-calls/{tool_call_id}", response_model=dict)
async def get_tool_call_via_approval_router(
    tool_call_id: uuid.UUID = Path(..., description="Tool Call ID"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from app.models.tool import ToolCall
    from sqlalchemy import select

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
