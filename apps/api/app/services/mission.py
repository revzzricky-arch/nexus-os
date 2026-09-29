"""
MissionService - Phase 2B-2 Mission API + EventBus Foundation

Responsibilities:
- create mission
- list missions
- retrieve mission
- update mission state
- cancel mission
- pause/resume where valid
- validate lifecycle transitions
- emit appropriate events

No HTTP-specific logic, async SQLAlchemy, explicit transition validator
Lifecycle vocabulary reconciled in Phase 2B-1: draft, decomposing, planned, running, awaiting_approval, paused, completed, failed, cancelled, archived
No second status vocabulary
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.mission import Mission
from app.schemas.mission import MissionCreate, MissionUpdate, MissionStatus, MissionTemplate
from app.schemas.event import EventCreate, EventType, EventSource
from app.core.exceptions import MissionNotFoundError, InvalidTransitionError, ValidationError
from app.services.event_bus import EventBusService

# Explicit transition validator - allowed transitions
# Examples from spec:
# draft -> decomposing
# decomposing -> planned
# planned -> running
# running -> paused
# running -> awaiting_approval
# running -> completed
# running -> failed
# running -> cancelled
# paused -> running
# paused -> cancelled
# Plus additional valid transitions for completeness and future
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"decomposing", "cancelled", "archived"},
    "decomposing": {"planned", "failed", "cancelled"},
    "planned": {"running", "failed", "cancelled", "archived"},
    "running": {"paused", "awaiting_approval", "completed", "failed", "cancelled"},
    "awaiting_approval": {"running", "paused", "failed", "cancelled", "completed"},
    "paused": {"running", "cancelled", "failed", "archived"},
    "completed": {"archived"},
    "failed": {"archived", "cancelled"},
    "cancelled": {"archived"},
    "archived": set(),  # terminal, no outgoing
}

# Terminal states should not transition back to active unless architecture explicitly supports it
TERMINAL_STATES = {"completed", "failed", "cancelled", "archived"}


class MissionService:
    def __init__(self, event_bus: EventBusService):
        self.event_bus = event_bus

    def validate_transition(self, from_status: str, to_status: str) -> None:
        """Validate lifecycle transition, raise InvalidTransitionError if invalid"""
        if from_status == to_status:
            return  # same status is idempotent, allow

        allowed = ALLOWED_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise InvalidTransitionError(from_status, to_status)

        # Terminal states should not go back to active unless explicitly allowed
        # Our ALLOWED_TRANSITIONS already enforces this, but extra safety
        if from_status in TERMINAL_STATES and to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
            raise InvalidTransitionError(from_status, to_status, details={"reason": "terminal state cannot transition to active"})

    async def create_mission(
        self,
        session: AsyncSession,
        mission_create: MissionCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Mission:
        """Create mission with validation, default status draft, emit mission_created"""
        # Validate title
        if not mission_create.title or not mission_create.title.strip():
            raise ValidationError("Title is required", details={"field": "title"})

        # Validate goal
        if not mission_create.goal or not mission_create.goal.strip():
            raise ValidationError("Goal is required", details={"field": "goal"})

        # Validate template is enum (Pydantic already validates, but extra safety)
        try:
            template = MissionTemplate(mission_create.template)
        except ValueError:
            raise ValidationError(f"Invalid template: {mission_create.template}", details={"field": "template"})

        mission = Mission(
            id=uuid.uuid4(),
            user_id=user_id,
            title=mission_create.title.strip(),
            goal=mission_create.goal.strip(),
            status="draft",
            template=template.value,
            dag=None,
            approval_policy=mission_create.approval_policy.model_dump() if mission_create.approval_policy else {"shell_always_approval": True},
            budget_tokens=mission_create.budget_tokens,
            budget_cost_cents=mission_create.budget_cost_cents,
            cost_tokens=0,
            cost_cents=0,
        )

        session.add(mission)
        await session.flush()
        await session.refresh(mission)

        # Emit mission_created event
        await self.event_bus.emit(
            session,
            EventCreate(
                type=EventType.mission_created,
                source=EventSource.system,
                mission_id=mission.id,
                payload={
                    "mission_id": str(mission.id),
                    "title": mission.title,
                    "goal": mission.goal,
                    "template": mission.template,
                    "status": mission.status,
                },
                metadata={"user_id": str(user_id) if user_id else None},
            ),
        )

        return mission

    async def list_missions(
        self,
        session: AsyncSession,
        status: Optional[str] = None,
        template: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Mission], int]:
        """List missions with pagination, optional status filtering, deterministic ordering"""
        # Validate limit/offset
        if limit < 1 or limit > 100:
            limit = 20
        if offset < 0:
            offset = 0

        base_query = select(Mission)
        count_query = select(func.count()).select_from(Mission)

        # Optional status filtering
        if status:
            # Validate status is known
            if status not in [s.value for s in MissionStatus]:
                raise ValidationError(f"Invalid status filter: {status}", details={"field": "status"})
            base_query = base_query.where(Mission.status == status)
            count_query = count_query.where(Mission.status == status)

        if template:
            if template not in [t.value for t in MissionTemplate]:
                raise ValidationError(f"Invalid template filter: {template}", details={"field": "template"})
            base_query = base_query.where(Mission.template == template)
            count_query = count_query.where(Mission.template == template)

        # Total count
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Deterministic ordering: created_at DESC + id DESC (newest first, stable)
        base_query = base_query.order_by(Mission.created_at.desc(), Mission.id.desc())
        base_query = base_query.limit(limit).offset(offset)

        result = await session.execute(base_query)
        missions = result.scalars().all()

        return list(missions), total

    async def get_mission(self, session: AsyncSession, mission_id: uuid.UUID) -> Mission:
        """Retrieve mission, 404 with typed error if missing"""
        result = await session.execute(select(Mission).where(Mission.id == mission_id))
        mission = result.scalar_one_or_none()

        if not mission:
            raise MissionNotFoundError(mission_id)

        return mission

    async def update_mission(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
        mission_update: MissionUpdate,
    ) -> Mission:
        """Update mission with explicit field allowlist, validate status transition, emit mission_status_changed"""
        mission = await self.get_mission(session, mission_id)

        from_status = mission.status

        # Allow only explicitly supported fields: status, title
        if mission_update.title is not None:
            if not mission_update.title.strip():
                raise ValidationError("Title cannot be empty", details={"field": "title"})
            mission.title = mission_update.title.strip()

        if mission_update.status is not None:
            to_status = mission_update.status.value if isinstance(mission_update.status, MissionStatus) else mission_update.status

            # Validate transition
            self.validate_transition(from_status, to_status)

            # Update
            mission.status = to_status
            mission.updated_at = datetime.now(timezone.utc)

            # Emit mission_status_changed when status changes
            if from_status != to_status:
                await self.event_bus.emit(
                    session,
                    EventCreate(
                        type=EventType.mission_status_changed,
                        source=EventSource.system,
                        mission_id=mission.id,
                        payload={
                            "mission_id": str(mission.id),
                            "from": from_status,
                            "to": to_status,
                        },
                    ),
                )

        await session.flush()
        await session.refresh(mission)

        return mission

    async def cancel_mission(self, session: AsyncSession, mission_id: uuid.UUID) -> Mission:
        """
        Cancel mission - idempotent if already cancelled
        Otherwise validate transition and persist cancelled, emit mission_status_changed
        """
        mission = await self.get_mission(session, mission_id)

        from_status = mission.status

        # Idempotent if already cancelled
        if from_status == "cancelled":
            return mission

        # Validate transition to cancelled
        try:
            self.validate_transition(from_status, "cancelled")
        except InvalidTransitionError:
            # If already in terminal that allows archived but not cancelled, check if we can still cancel
            # For example, completed -> cancelled is not allowed per our matrix, but we should allow cancel from most active states
            # Our matrix already allows cancelled from draft, decomposing, planned, running, awaiting_approval, paused, failed
            # But not from completed/archived - those are terminal and should not be cancellable
            # So if invalid, we raise
            raise

        mission.status = "cancelled"
        mission.updated_at = datetime.now(timezone.utc)

        await session.flush()
        await session.refresh(mission)

        # Emit mission_status_changed
        await self.event_bus.emit(
            session,
            EventCreate(
                type=EventType.mission_status_changed,
                source=EventSource.system,
                mission_id=mission.id,
                payload={
                    "mission_id": str(mission.id),
                    "from": from_status,
                    "to": "cancelled",
                },
            ),
        )

        return mission


# Singleton with EventBus dependency
# Note: EventBus is singleton, MissionService uses it
# For testing, can inject mock EventBus
from app.services.event_bus import event_bus_service

mission_service = MissionService(event_bus=event_bus_service)
