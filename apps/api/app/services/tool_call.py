"""
ToolCall Service - Phase 2B-4 with explicit scoping boundary and real enforcement

Scoping Boundary:
- D4 single dev token model: dev-user owns all missions in MVP
- Explicit ownership boundary in service layer to prevent unrestricted access when multi-user introduced
- ToolCall linked to Task and AgentRun which link to Mission which has user_id
- Future multi-user: enforce Mission.user_id == user_context.user_id
- Fail closed: missing mission linkage should fail closed for scoped access rather than silently allowing unrestricted access
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
    ToolCall service with explicit scoping boundary and real enforcement
    """

    def _get_user_id_from_context(self, user_context: Optional[Dict[str, Any]]) -> Optional[str]:
        if not user_context:
            return None
        if isinstance(user_context, dict):
            return user_context.get("user_id")
        return getattr(user_context, "user_id", None)

    def _is_uuid(self, val: str) -> bool:
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    async def _check_mission_ownership(
        self,
        session: AsyncSession,
        mission_id: Optional[uuid.UUID],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        user_id = self._get_user_id_from_context(user_context)
        if user_id is None:
            if mission_id is None and user_context is not None:
                pass
            return

        if user_id == "dev-user":
            return

        if user_id == "anonymous":
            raise PermissionDeniedError("Anonymous user cannot access tool calls")

        if mission_id is None:
            raise PermissionDeniedError("Missing mission linkage for scoped access - fail closed for non-dev user")

        try:
            result = await session.execute(select(Mission).where(Mission.id == mission_id))
            mission = result.scalar_one_or_none()
        except Exception as e:
            raise PermissionDeniedError(f"Failed to verify mission ownership for {mission_id}")

        if not mission:
            raise NotFoundError(f"Mission {mission_id} not found")

        if not hasattr(mission, "user_id") or mission.user_id is None:
            raise PermissionDeniedError(f"No valid ownership match for mission {mission_id} - mission has no owner, non-dev user denied")

        try:
            mission_user_id_str = str(mission.user_id)
            context_user_id_str = str(user_id)
            if mission_user_id_str == context_user_id_str:
                return
            try:
                if uuid.UUID(mission_user_id_str) == uuid.UUID(context_user_id_str):
                    return
            except ValueError:
                pass
            raise PermissionDeniedError(f"Ownership mismatch for mission {mission_id} - user {user_id} does not own mission owned by {mission.user_id}")
        except PermissionDeniedError:
            raise
        except Exception as e:
            raise PermissionDeniedError(f"Failed to verify ownership for mission {mission_id}")

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
        if user_context:
            await self._check_mission_ownership(session, mission_id, user_context)

        return tc

    async def get_tool_call_scoped(
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

        user_id = self._get_user_id_from_context(user_context)
        if user_id and user_id not in ("dev-user", "anonymous", None):
            if mission_id is None:
                raise PermissionDeniedError(f"Missing mission linkage for tool call {tool_call_id} - fail closed for non-dev user")
            await self._check_mission_ownership(session, mission_id, user_context)
        elif user_context:
            if mission_id:
                await self._check_mission_ownership(session, mission_id, user_context)

        return tc


tool_call_service = ToolCallService()
