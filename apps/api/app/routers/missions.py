"""
Missions Router - Phase 2B-2 Mission API + EventBus Foundation

Implements:
POST /api/v1/missions - create mission
GET /api/v1/missions - list with pagination + status filter deterministic
GET /api/v1/missions/{id} - retrieve mission + task summary 404 typed
PATCH /api/v1/missions/{id} - allow explicitly supported fields validate transition emit mission_status_changed
POST /api/v1/missions/{id}/cancel - idempotent cancel
GET /api/v1/missions/{id}/tasks - list tasks for mission no cross-mission leak
GET /api/v1/missions/{id}/events - ordered deterministic filters type/from/to/limit/offset/last_event_id mandatory scoping

Error model: {"error": {"code": "...", "message": "...", "details": {}}}
Bearer Auth D4 reused
"""

import uuid
from datetime import datetime
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.dependencies import get_db, get_current_user
from app.schemas.mission import MissionCreate, MissionUpdate, MissionResponse, MissionStatus
from app.schemas.task import TaskResponse
from app.schemas.event import EventResponse
from app.schemas.common import PaginatedResponse, ErrorResponse
from app.services.mission import mission_service
from app.services.event_bus import event_bus_service
from app.core.exceptions import DomainError
from app.models.mission import Mission
from app.models.task import Task
from app.models.event import Event

router = APIRouter(prefix="/missions", tags=["missions"])


def _handle_domain_error(e: DomainError):
    raise HTTPException(
        status_code=e.status_code,
        detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
    )


@router.post("/", response_model=MissionResponse, status_code=201)
async def create_mission(
    payload: MissionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        mission = await mission_service.create_mission(db, payload, user_id=None)
        return mission
    except DomainError as e:
        _handle_domain_error(e)
    except Exception as ex:
        # Do not leak internals
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "validation_error", "message": str(ex), "details": {}}},
        )


@router.get("/", response_model=PaginatedResponse[MissionResponse])
async def list_missions(
    status: Optional[str] = Query(None, description="Filter by status"),
    template: Optional[str] = Query(None, description="Filter by template"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        missions, total = await mission_service.list_missions(
            db, status=status, template=template, limit=limit, offset=offset
        )
        return {
            "data": missions,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/{mission_id}", response_model=dict)
async def get_mission(
    mission_id: uuid.UUID = Path(..., description="Mission ID"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        mission = await mission_service.get_mission(db, mission_id)

        # Task summary for dashboard
        task_count_query = select(func.count()).select_from(Task).where(Task.mission_id == mission_id)
        task_count_result = await db.execute(task_count_query)
        task_total = task_count_result.scalar() or 0

        # Status breakdown
        task_status_query = select(Task.status, func.count()).where(Task.mission_id == mission_id).group_by(Task.status)
        task_status_result = await db.execute(task_status_query)
        status_breakdown = {row[0]: row[1] for row in task_status_result.all()}

        return {
            "mission": MissionResponse.model_validate(mission),
            "task_summary": {
                "total": task_total,
                "by_status": status_breakdown,
            },
        }
    except DomainError as e:
        _handle_domain_error(e)


@router.patch("/{mission_id}", response_model=MissionResponse)
async def update_mission(
    payload: MissionUpdate,
    mission_id: uuid.UUID = Path(..., description="Mission ID"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        mission = await mission_service.update_mission(db, mission_id, payload)
        return mission
    except DomainError as e:
        _handle_domain_error(e)


@router.post("/{mission_id}/cancel", response_model=MissionResponse)
async def cancel_mission(
    mission_id: uuid.UUID = Path(..., description="Mission ID"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Idempotent cancel - if already cancelled returns existing mission
    Validates transition, persists cancelled, emits mission_status_changed
    """
    try:
        mission = await mission_service.cancel_mission(db, mission_id)
        return mission
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/{mission_id}/tasks", response_model=PaginatedResponse[TaskResponse])
async def list_mission_tasks(
    mission_id: uuid.UUID = Path(..., description="Mission ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by task status"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    List tasks for mission - verify mission exists, no cross-mission leak
    """
    try:
        # Verify mission exists
        await mission_service.get_mission(db, mission_id)

        # Query tasks scoped to mission_id (mandatory)
        base_query = select(Task).where(Task.mission_id == mission_id)
        count_query = select(func.count()).select_from(Task).where(Task.mission_id == mission_id)

        if status:
            base_query = base_query.where(Task.status == status)
            count_query = count_query.where(Task.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Deterministic ordering: created_at ASC + id ASC (or DESC for newest? use ASC for stable task order)
        base_query = base_query.order_by(Task.created_at.asc(), Task.id.asc())
        base_query = base_query.limit(limit).offset(offset)

        result = await db.execute(base_query)
        tasks = result.scalars().all()

        return {
            "data": tasks,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except DomainError as e:
        _handle_domain_error(e)


@router.get("/{mission_id}/events", response_model=PaginatedResponse[EventResponse])
async def list_mission_events(
    mission_id: uuid.UUID = Path(..., description="Mission ID"),
    event_type: Optional[str] = Query(None, alias="type", description="Filter by event type"),
    from_timestamp: Optional[datetime] = Query(None, alias="from", description="Filter from timestamp"),
    to_timestamp: Optional[datetime] = Query(None, alias="to", description="Filter to timestamp"),
    last_event_id: Optional[uuid.UUID] = Query(None, description="Replay after this event ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    List events for mission with mandatory scoping
    Ordered deterministically: timestamp ASC + id ASC
    Filters: type, from, to, last_event_id, limit, offset
    last_event_id scoped safely - if doesn't belong to mission, handle safely no leak
    """
    try:
        # Verify mission exists
        await mission_service.get_mission(db, mission_id)

        events, total = await event_bus_service.list(
            db,
            mission_id=mission_id,
            event_type=event_type,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            last_event_id=last_event_id,
            limit=limit,
            offset=offset,
        )

        return {
            "data": events,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except DomainError as e:
        _handle_domain_error(e)
