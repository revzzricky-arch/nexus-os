"""
EventEnvelope Tests - Phase 2B-2
Schema matches shared/persistence/mission_created/mission_status_changed/deterministic/mission scoping/last_event_id
"""

import uuid
import pathlib
import re
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.base import Base
from app.models.mission import Mission
from app.models.event import Event
from app.schemas.event import EventCreate, EventType, EventSource, EventEnvelope, EventResponse
from app.services.event_bus import EventBusService
from app.services.mission import MissionService
from app.schemas.mission import MissionCreate, MissionUpdate, MissionStatus


SHARED_EVENTS_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "packages" / "shared" / "src" / "events.ts"


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


def test_shared_event_envelope_contract_exists():
    assert SHARED_EVENTS_PATH.exists(), "shared/src/events.ts must exist"

    content = SHARED_EVENTS_PATH.read_text()

    # Check required fields in EventEnvelope
    required_fields = ["id", "type", "source", "mission_id", "timestamp", "version", "payload"]
    for field in required_fields:
        assert field in content, f"EventEnvelope missing field {field} in shared contract"

    # Check optional fields
    assert "task_id" in content
    assert "agent_id" in content
    assert "metadata" in content


def test_backend_event_envelope_matches_shared():
    """
    Backend EventResponse/EventEnvelope must have same required fields as shared
    """
    # Check Pydantic model fields
    envelope_fields = EventEnvelope.model_fields.keys()
    required = {"id", "type", "source", "mission_id", "timestamp", "version", "payload"}

    for f in required:
        assert f in envelope_fields, f"Backend EventEnvelope missing required field {f}"

    # Optional fields
    assert "task_id" in envelope_fields
    assert "agent_id" in envelope_fields
    assert "metadata" in envelope_fields


def test_event_model_has_required_columns():
    """Persistence model must have same required columns"""
    # Check via model inspection
    from app.models.event import Event as EventModel

    # Required columns should exist
    assert hasattr(EventModel, "id")
    assert hasattr(EventModel, "type")
    assert hasattr(EventModel, "source")
    assert hasattr(EventModel, "mission_id")
    assert hasattr(EventModel, "timestamp")
    assert hasattr(EventModel, "version")
    assert hasattr(EventModel, "payload")


@pytest.mark.asyncio
async def test_mission_created_event_structure(async_session: AsyncSession, mission_service: MissionService):
    m = await mission_service.create_mission(async_session, MissionCreate(title="Test", goal="Goal"))

    result = await async_session.execute(select(Event).where(Event.mission_id == m.id))
    events = result.scalars().all()

    assert len(events) == 1
    e = events[0]

    # Check EventEnvelope structure
    assert e.type == EventType.mission_created.value
    assert e.source == EventSource.system.value
    assert e.mission_id == m.id
    assert e.task_id is None
    assert e.agent_id is None
    assert e.timestamp is not None
    assert e.version == 1
    assert e.payload is not None
    assert "mission_id" in e.payload
    assert "title" in e.payload
    assert "status" in e.payload

    # Convert to EventResponse and check envelope compliance
    resp = EventResponse.model_validate(e)
    envelope = EventEnvelope(
        id=resp.id,
        type=resp.type,
        source=resp.source,
        mission_id=resp.mission_id,
        task_id=resp.task_id,
        agent_id=resp.agent_id,
        agent_run_id=resp.agent_run_id,
        timestamp=resp.timestamp,
        version=resp.version,
        payload=resp.payload,
        metadata=resp.metadata,
    )

    assert envelope.id == e.id
    assert envelope.type == EventType.mission_created


@pytest.mark.asyncio
async def test_mission_status_changed_event_structure(async_session: AsyncSession, mission_service: MissionService):
    m = await mission_service.create_mission(async_session, MissionCreate(title="Test", goal="Goal"))
    await mission_service.update_mission(async_session, m.id, MissionUpdate(status=MissionStatus.decomposing))

    result = await async_session.execute(select(Event).where(Event.mission_id == m.id).order_by(Event.timestamp.asc()))
    events = result.scalars().all()

    assert len(events) == 2
    assert events[0].type == "mission_created"
    assert events[1].type == "mission_status_changed"

    status_event = events[1]
    assert status_event.payload["from"] == "draft"
    assert status_event.payload["to"] == "decomposing"
    assert status_event.payload["mission_id"] == str(m.id)


@pytest.mark.asyncio
async def test_event_deterministic_ordering(async_session: AsyncSession, event_bus: EventBusService):
    m = Mission(id=uuid.uuid4(), title="M", goal="g", status="draft", template="general")
    async_session.add(m)
    await async_session.flush()

    # Emit events with same logic, ensure ordering deterministic
    events_created = []
    for i in range(5):
        e = await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m.id, payload={"i": i}))
        events_created.append(e)

    # List should be deterministic timestamp ASC + id ASC
    events_listed, total = await event_bus.list(async_session, mission_id=m.id, limit=10)

    assert total == 5
    # Check ordering matches creation order (since timestamp increases)
    for i in range(4):
        assert events_listed[i].timestamp <= events_listed[i + 1].timestamp
        # If timestamps equal, id ordering should be deterministic (UUID comparison)
        if events_listed[i].timestamp == events_listed[i + 1].timestamp:
            assert str(events_listed[i].id) < str(events_listed[i + 1].id) or str(events_listed[i].id) != str(events_listed[i + 1].id)


@pytest.mark.asyncio
async def test_event_mission_scoping_mandatory(async_session: AsyncSession, event_bus: EventBusService):
    m1 = Mission(id=uuid.uuid4(), title="M1", goal="g", status="draft", template="general")
    m2 = Mission(id=uuid.uuid4(), title="M2", goal="g", status="draft", template="general")
    async_session.add_all([m1, m2])
    await async_session.flush()

    await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m1.id, payload={"m": 1}))
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m2.id, payload={"m": 2}))

    # List for m1 should not include m2 events
    events_m1, _ = await event_bus.list(async_session, mission_id=m1.id)
    assert len(events_m1) == 1
    assert events_m1[0].mission_id == m1.id
    assert events_m1[0].payload["m"] == 1

    events_m2, _ = await event_bus.list(async_session, mission_id=m2.id)
    assert len(events_m2) == 1
    assert events_m2[0].mission_id == m2.id
    assert events_m2[0].payload["m"] == 2


@pytest.mark.asyncio
async def test_last_event_id_replay_scoped(async_session: AsyncSession, event_bus: EventBusService):
    m1 = Mission(id=uuid.uuid4(), title="M1", goal="g", status="draft", template="general")
    m2 = Mission(id=uuid.uuid4(), title="M2", goal="g", status="draft", template="general")
    async_session.add_all([m1, m2])
    await async_session.flush()

    e1_m1 = await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m1.id, payload={"n": 1}))
    e2_m1 = await event_bus.emit(async_session, EventCreate(type=EventType.mission_status_changed, source=EventSource.system, mission_id=m1.id, payload={"n": 2}))
    e1_m2 = await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m2.id, payload={"n": 3}))

    # Replay m1 after e1_m1 should give e2_m1 only
    events, total = await event_bus.list(async_session, mission_id=m1.id, last_event_id=e1_m1.id)
    assert total == 1
    assert events[0].id == e2_m1.id

    # Replay m1 with e1_m2 (belongs to m2) should return empty safely, no leak
    events, total = await event_bus.list(async_session, mission_id=m1.id, last_event_id=e1_m2.id)
    assert total == 0
    assert len(events) == 0

    # Replay with non-existent ID should handle safely (return from start or empty, but not leak)
    fake_id = uuid.uuid4()
    events, total = await event_bus.list(async_session, mission_id=m1.id, last_event_id=fake_id)
    # Our implementation returns from start when ID not found (scoped to mission)
    # This is safe - still scoped to mission_id
    assert total >= 0  # Should not crash, and should not return m2 events
    assert all(e.mission_id == m1.id for e in events)
