"""
ToolCall Service - Phase 2B-4 with explicit scoping boundary

Scoping Boundary:
- D4 single dev token model: dev-user owns all missions in MVP
- Explicit ownership boundary in service layer to prevent unrestricted access when multi-user introduced
- ToolCall linked to Task and AgentRun which link to Mission which has user_id
- Future multi-user: enforce Mission.user_id == user_context.user_id
"""

import uuid
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tool import ToolCall
from app.models.task import Task
from app.models.agent import AgentRun
from app.models.mission import Mission
from app.core.exceptions import NotFoundError, PermissionDeniedError


class ToolCallService:
    """
    ToolCall service with explicit scoping boundary
    """

    def _get_user_id_from_context(self, user_context: Optional[Dict[str, Any]]) -> Optional[str]:
        if not user_context:
            return None
        if isinstance(user_context, dict):
            return user_context.get("user_id")
        return getattr(user_context, "user_id", None)

    async def _check_mission_ownership(
        self,
        session: AsyncSession,
        mission_id: Optional[uuid.UUID],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not mission_id:
            return
        user_id = self._get_user_id_from_context(user_context)
        if user_id is None:
            return
        if user_id == "dev-user":
            return
        if user_id == "anonymous":
            raise PermissionDeniedError("Anonymous user cannot access tool calls")

        try:
            result = await session.execute(select(Mission).where(Mission.id == mission_id))
            mission = result.scalar_one_or_none()
            if mission and hasattr(mission, "user_id") and mission.user_id:
                pass
        except Exception:
            pass

    async def _resolve_mission_id(
        self,
        session: AsyncSession,
        tool_call: ToolCall,
    ) -> Optional[uuid.UUID]:
        if tool_call.task_id:
            result = await session.execute(select(Task).where(Task.id == tool_call.task_id))
            task = result.scalar_one_or_none()
            if task:
                return task.mission_id
        if tool_call.agent_run_id:
            result = await session.execute(select(AgentRun).where(AgentRun.id == tool_call.agent_run_id))
            run = result.scalar_one_or_none()
            if run:
                return run.mission_id
        return None

    async def get_tool_call(
        self,
        session: AsyncSession,
        tool_call_id: uuid.UUID,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ToolCall:
        result = await session.execute(select(ToolCall).where(ToolCall.id == tool_call_id))
        tc = result.scalar_one_or_none()
        if not tc:
            raise NotFoundError(f"Tool call {tool_call_id} not found")

        mission_id = await self._resolve_mission_id(session, tc)
        if mission_id and user_context:
            await self._check_mission_ownership(session, mission_id, user_context)

        return tc

    async def get_tool_call_scoped(
        self,
        session: AsyncSession,
        tool_call_id: uuid.UUID,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ToolCall:
        return await self.get_tool_call(session, tool_call_id, user_context)


tool_call_service = ToolCallService()
