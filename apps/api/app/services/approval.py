"""
ApprovalService - Phase 2B-4 Real Implementation with Postgres persistence

Persistent using approvals table and tool_calls
Methods: create_approval, get_approval, list_approvals, decide_approval, expire_approval
Statuses: pending, approved, denied, expired
Record mission/task/agent run/tool call/requested action/args/reasoning/risk level/reviewer/decision/timestamps/comment/edited_args
Source of truth Postgres, UI never authoritative
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.tool import Approval, ToolCall
from app.schemas.tool import ApprovalStatus, ApprovalType
from app.core.exceptions import NotFoundError, ValidationError


class ApprovalService:
    """
    Approval persistence service - source of truth Postgres
    """

    async def create_approval(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
        task_id: Optional[uuid.UUID] = None,
        agent_run_id: Optional[uuid.UUID] = None,
        tool_call_id: Optional[uuid.UUID] = None,
        type: str = "tool",
        requested_by: Optional[str] = None,
        requested_payload: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> Approval:
        """
        Create approval request
        requested_payload includes action, args, reasoning, risk_level
        """
        # Default expiry 24h
        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        approval = Approval(
            id=uuid.uuid4(),
            mission_id=mission_id,
            task_id=task_id,
            agent_run_id=agent_run_id,
            tool_call_id=tool_call_id,
            type=type,
            status="pending",
            requested_by=requested_by,
            requested_payload=requested_payload,
            expires_at=expires_at,
        )
        session.add(approval)
        await session.flush()
        await session.refresh(approval)
        return approval

    async def get_approval(
        self,
        session: AsyncSession,
        approval_id: uuid.UUID,
    ) -> Optional[Approval]:
        result = await session.execute(select(Approval).where(Approval.id == approval_id))
        return result.scalar_one_or_none()

    async def list_approvals(
        self,
        session: AsyncSession,
        mission_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[Approval], int]:
        from sqlalchemy import func

        query = select(Approval)
        count_query = select(func.count()).select_from(Approval)

        filters = []
        if mission_id:
            filters.append(Approval.mission_id == mission_id)
        if status:
            filters.append(Approval.status == status)

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        query = query.order_by(Approval.created_at.desc()).limit(limit).offset(offset)

        result = await session.execute(query)
        approvals = list(result.scalars().all())

        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        return approvals, total

    async def decide_approval(
        self,
        session: AsyncSession,
        approval_id: uuid.UUID,
        decision: str,
        reviewed_by: Optional[uuid.UUID] = None,
        review_comment: Optional[str] = None,
        edited_args: Optional[Dict[str, Any]] = None,
    ) -> Approval:
        """
        Decide approval - approved or denied
        If approved with edited_args, those args should be used for execution
        """
        if decision not in ["approved", "denied"]:
            raise ValidationError(f"Invalid decision {decision}, must be approved or denied")

        approval = await self.get_approval(session, approval_id)
        if not approval:
            raise NotFoundError(f"Approval {approval_id} not found")

        if approval.status != "pending":
            raise ValidationError(f"Approval {approval_id} already decided: {approval.status}")

        # Check expiry - handle both naive and aware datetimes (sqlite returns naive)
        if approval.expires_at:
            now = datetime.now(timezone.utc)
            expires = approval.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < now:
                # Expire it
                approval.status = "expired"
                await session.flush()
                raise ValidationError(f"Approval {approval_id} expired")

        approval.status = decision
        approval.reviewed_by = reviewed_by
        approval.review_comment = review_comment
        approval.edited_args = edited_args
        approval.reviewed_at = datetime.now(timezone.utc)

        await session.flush()
        await session.refresh(approval)
        return approval

    async def expire_approval(
        self,
        session: AsyncSession,
        approval_id: uuid.UUID,
    ) -> Approval:
        approval = await self.get_approval(session, approval_id)
        if not approval:
            raise NotFoundError(f"Approval {approval_id} not found")

        if approval.status != "pending":
            raise ValidationError(f"Approval {approval_id} not pending, cannot expire")

        approval.status = "expired"
        approval.reviewed_at = datetime.now(timezone.utc)

        await session.flush()
        await session.refresh(approval)
        return approval

    async def expire_stale_approvals(
        self,
        session: AsyncSession,
    ) -> int:
        """
        Expire all pending approvals past expires_at
        Returns count expired
        """
        now = datetime.now(timezone.utc)
        result = await session.execute(select(Approval).where(Approval.status == "pending"))
        all_pending = list(result.scalars().all())
        count = 0
        for approval in all_pending:
            if approval.expires_at:
                expires = approval.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if expires < now:
                    approval.status = "expired"
                    approval.reviewed_at = now
                    count += 1
        if count > 0:
            await session.flush()
        return count

    async def get_pending_for_mission(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
    ) -> List[Approval]:
        result = await session.execute(
            select(Approval).where(and_(Approval.mission_id == mission_id, Approval.status == "pending")).order_by(Approval.created_at.desc())
        )
        return list(result.scalars().all())


approval_service = ApprovalService()
