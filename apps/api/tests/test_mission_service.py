"""
MissionService Tests - Phase 2B-2
Lifecycle matrix, domain errors, event emission
No LLM/MCP/LangGraph
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.base import Base
from app.models.mission import Mission
from app.models.event import Event
from app.schemas.mission import MissionCreate, MissionUpdate, MissionStatus
from app.schemas.event import EventType
from app.services.mission import MissionService
from app.services.event_bus import EventBusService
from app.core.exceptions import MissionNotFoundError, InvalidTransitionError, ValidationError


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    try:
        await engine.dispose()
    except Exception:
        pass


@pytest.fixture
async def async_session(async_engine):
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def event_bus():
    return EventBusService()


@pytest.fixture
def mission_service(event_bus):
    return MissionService(event_bus=event_bus)


@pytest.mark.asyncio
async def test_create_mission_success(async_session: AsyncSession, mission_service: MissionService):
    create = MissionCreate(title="Test Mission", goal="Test goal")
    mission = await mission_service.create_mission(async_session, create)

    assert mission.title == "Test Mission"
    assert mission.status == "draft"
    assert mission.template == "general"

    # Check event emitted
    result = await async_session.execute(select(Event).where(Event.mission_id == mission.id))
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].type == "mission_created"
    assert events[0].payload["title"] == "Test Mission"


@pytest.mark.asyncio
async def test_create_mission_validation(async_session: AsyncSession, mission_service: MissionService):
    # Empty title should raise ValidationError (via Pydantic or service)
    with pytest.raises((ValidationError, Exception)):
        create = MissionCreate(title="", goal="goal")
        await mission_service.create_mission(async_session, create)

    with pytest.raises((ValidationError, Exception)):
        create = MissionCreate(title="title", goal="")
        await mission_service.create_mission(async_session, create)


@pytest.mark.asyncio
async def test_lifecycle_matrix_valid_transitions(async_session: AsyncSession, mission_service: MissionService):
    """
    Test explicit transition validator per spec:
    draft->decomposing, decomposing->planned, planned->running, running->paused/awaiting_approval/completed/failed/cancelled, paused->running/cancelled
    """
    # draft -> decomposing
    m = await mission_service.create_mission(async_session, MissionCreate(title="T1", goal="g"))
    assert m.status == "draft"

    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.decomposing))
    assert m.status == "decomposing"

    # decomposing -> planned
    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.planned))
    assert m.status == "planned"

    # planned -> running
    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.running))
    assert m.status == "running"

    # running -> paused
    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.paused))
    assert m.status == "paused"

    # paused -> running
    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.running))
    assert m.status == "running"

    # running -> awaiting_approval
    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.awaiting_approval))
    assert m.status == "awaiting_approval"

    # awaiting_approval -> running
    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.running))
    assert m.status == "running"

    # running -> completed
    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.completed))
    assert m.status == "completed"

    # completed -> archived (valid)
    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.archived))
    assert m.status == "archived"


@pytest.mark.asyncio
async def test_lifecycle_matrix_invalid_transitions(async_session: AsyncSession, mission_service: MissionService):
    m = await mission_service.create_mission(async_session, MissionCreate(title="T2", goal="g"))

    # draft -> running should be invalid
    with pytest.raises(InvalidTransitionError):
        await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.running))

    # draft -> completed invalid
    with pytest.raises(InvalidTransitionError):
        await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.completed))

    # Move to running
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.decomposing))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.planned))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.running))

    # running -> draft invalid
    with pytest.raises(InvalidTransitionError):
        await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.draft))

    # running -> decomposing invalid
    with pytest.raises(InvalidTransitionError):
        await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.decomposing))


@pytest.mark.asyncio
async def test_terminal_states_no_transition_back(async_session: AsyncSession, mission_service: MissionService):
    m = await mission_service.create_mission(async_session, MissionCreate(title="T3", goal="g"))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.decomposing))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.planned))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.running))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.completed))

    # completed -> running should be invalid (terminal)
    with pytest.raises(InvalidTransitionError):
        await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.running))

    # completed -> draft invalid
    with pytest.raises(InvalidTransitionError):
        await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.draft))

    # completed -> archived valid
    m = await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.archived))
    assert m.status == "archived"

    # archived -> anything invalid
    with pytest.raises(InvalidTransitionError):
        await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.running))


@pytest.mark.asyncio
async def test_cancel_idempotent(async_session: AsyncSession, mission_service: MissionService):
    m = await mission_service.create_mission(async_session, MissionCreate(title="T4", goal="g"))

    # cancel from draft (allowed)
    m = await mission_service.cancel_mission(async_session, m.id)
    assert m.status == "cancelled"

    # cancel again idempotent
    m2 = await mission_service.cancel_mission(async_session, m.id)
    assert m2.status == "cancelled"
    assert m2.id == m.id


@pytest.mark.asyncio
async def test_cancel_invalid_from_completed(async_session: AsyncSession, mission_service: MissionService):
    m = await mission_service.create_mission(async_session, MissionCreate(title="T5", goal="g"))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.decomposing))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.planned))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.running))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.completed))

    with pytest.raises(InvalidTransitionError):
        await mission_service.cancel_mission(async_session, m.id)


@pytest.mark.asyncio
async def test_get_mission_not_found(async_session: AsyncSession, mission_service: MissionService):
    with pytest.raises(MissionNotFoundError):
        await mission_service.get_mission(async_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_list_missions_pagination(async_session: AsyncSession, mission_service: MissionService):
    for i in range(5):
        await mission_service.create_mission(async_session, MissionCreate(title=f"M{i}", goal="g"))

    missions, total = await mission_service.list_missions(async_session, limit=2, offset=0)
    assert total == 5
    assert len(missions) == 2

    missions2, total2 = await mission_service.list_missions(async_session, limit=2, offset=2)
    assert total2 == 5
    assert len(missions2) == 2

    # deterministic ordering: ensure no overlap
    ids1 = {m.id for m in missions}
    ids2 = {m.id for m in missions2}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_event_emission_on_status_change(async_session: AsyncSession, mission_service: MissionService):
    m = await mission_service.create_mission(async_session, MissionCreate(title="T6", goal="g"))

    # 1 event for creation
    result = await async_session.execute(select(Event).where(Event.mission_id == m.id))
    assert len(result.scalars().all()) == 1

    # update to decomposing emits mission_status_changed
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.decomposing))

    result = await async_session.execute(select(Event).where(Event.mission_id == m.id).order_by(Event.timestamp.asc()))
    events = result.scalars().all()
    assert len(events) == 2
    assert events[0].type == "mission_created"
    assert events[1].type == "mission_status_changed"
    assert events[1].payload["from"] == "draft"
    assert events[1].payload["to"] == "decomposing"
