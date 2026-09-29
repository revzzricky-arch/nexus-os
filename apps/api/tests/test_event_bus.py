"""
EventBus Tests - Phase 2B-2
Emit persists, list, subscriber, Redis unavailable does not prevent DB persistence, deterministic
"""

import uuid
import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.base import Base
from app.models.mission import Mission
from app.models.event import Event
from app.schemas.event import EventCreate, EventType, EventSource
from app.services.event_bus import EventBusService
from app.config import settings


@pytest.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def event_bus():
    return EventBusService()


@pytest.fixture
async def mission_id(async_session: AsyncSession):
    m = Mission(
        id=uuid.uuid4(),
        title="Test",
        goal="Test goal",
        status="draft",
        template="general",
    )
    async_session.add(m)
    await async_session.flush()
    return m.id


@pytest.mark.asyncio
async def test_emit_persists(async_session: AsyncSession, event_bus: EventBusService, mission_id: uuid.UUID):
    create = EventCreate(
        type=EventType.mission_created,
        source=EventSource.system,
        mission_id=mission_id,
        payload={"title": "Test"},
    )
    event = await event_bus.emit(async_session, create)

    assert event.id is not None
    assert event.type == "mission_created"
    assert event.mission_id == mission_id

    # Verify persisted in DB
    result = await async_session.execute(select(Event).where(Event.id == event.id))
    persisted = result.scalar_one()
    assert persisted.type == "mission_created"


@pytest.mark.asyncio
async def test_list_deterministic_ordering(async_session: AsyncSession, event_bus: EventBusService, mission_id: uuid.UUID):
    # Emit 3 events
    for i in range(3):
        create = EventCreate(
            type=EventType.mission_created,
            source=EventSource.system,
            mission_id=mission_id,
            payload={"i": i},
        )
        await event_bus.emit(async_session, create)

    events, total = await event_bus.list(async_session, mission_id=mission_id, limit=10, offset=0)

    assert total == 3
    assert len(events) == 3
    # Deterministic ordering: timestamp ASC + id ASC, so i should be in order of emission (if same timestamp, id ordering still deterministic)
    # Check ordering is stable
    assert events[0].timestamp <= events[1].timestamp
    assert events[1].timestamp <= events[2].timestamp


@pytest.mark.asyncio
async def test_list_mission_scoping(async_session: AsyncSession, event_bus: EventBusService):
    # Create 2 missions
    m1 = Mission(id=uuid.uuid4(), title="M1", goal="g", status="draft", template="general")
    m2 = Mission(id=uuid.uuid4(), title="M2", goal="g", status="draft", template="general")
    async_session.add_all([m1, m2])
    await async_session.flush()

    # Emit events for each
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m1.id, payload={}))
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m1.id, payload={}))
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m2.id, payload={}))

    events_m1, total_m1 = await event_bus.list(async_session, mission_id=m1.id)
    events_m2, total_m2 = await event_bus.list(async_session, mission_id=m2.id)

    assert total_m1 == 2
    assert total_m2 == 1
    assert all(e.mission_id == m1.id for e in events_m1)
    assert all(e.mission_id == m2.id for e in events_m2)


@pytest.mark.asyncio
async def test_list_filters(async_session: AsyncSession, event_bus: EventBusService, mission_id: uuid.UUID):
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=mission_id, payload={}))
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_status_changed, source=EventSource.system, mission_id=mission_id, payload={"from": "draft", "to": "decomposing"}))
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_status_changed, source=EventSource.system, mission_id=mission_id, payload={"from": "decomposing", "to": "planned"}))

    events, total = await event_bus.list(async_session, mission_id=mission_id, event_type="mission_created")
    assert total == 1
    assert events[0].type == "mission_created"

    events, total = await event_bus.list(async_session, mission_id=mission_id, event_type="mission_status_changed")
    assert total == 2


@pytest.mark.asyncio
async def test_list_last_event_id_replay(async_session: AsyncSession, event_bus: EventBusService, mission_id: uuid.UUID):
    e1 = await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=mission_id, payload={"n": 1}))
    e2 = await event_bus.emit(async_session, EventCreate(type=EventType.mission_status_changed, source=EventSource.system, mission_id=mission_id, payload={"n": 2}))
    e3 = await event_bus.emit(async_session, EventCreate(type=EventType.mission_status_changed, source=EventSource.system, mission_id=mission_id, payload={"n": 3}))

    # Replay after e1 should return e2, e3
    events, total = await event_bus.list(async_session, mission_id=mission_id, last_event_id=e1.id)
    assert total == 2
    assert len(events) == 2
    assert events[0].id == e2.id
    assert events[1].id == e3.id


@pytest.mark.asyncio
async def test_last_event_id_wrong_mission_safety(async_session: AsyncSession, event_bus: EventBusService):
    m1 = Mission(id=uuid.uuid4(), title="M1", goal="g", status="draft", template="general")
    m2 = Mission(id=uuid.uuid4(), title="M2", goal="g", status="draft", template="general")
    async_session.add_all([m1, m2])
    await async_session.flush()

    e_m1 = await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m1.id, payload={}))
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=m2.id, payload={}))

    # Try to replay m2 events using m1's last_event_id - should return empty safely, no leak
    events, total = await event_bus.list(async_session, mission_id=m2.id, last_event_id=e_m1.id)
    assert total == 0
    assert len(events) == 0


@pytest.mark.asyncio
async def test_redis_unavailable_does_not_prevent_db_persistence(async_session: AsyncSession, event_bus: EventBusService, mission_id: uuid.UUID):
    """
    EventBus must not lose events when Redis unavailable - DB is source of truth
    We simulate by setting redis_url to invalid and ensuring emit still persists
    """
    # Save original
    original_redis_url = settings.redis_url
    settings.redis_url = "redis://invalid-host:6379/0"

    try:
        create = EventCreate(
            type=EventType.mission_created,
            source=EventSource.system,
            mission_id=mission_id,
            payload={"test": "redis down"},
        )
        event = await event_bus.emit(async_session, create)

        # Should still persist in DB even if Redis fails
        result = await async_session.execute(select(Event).where(Event.id == event.id))
        persisted = result.scalar_one_or_none()
        assert persisted is not None
        assert persisted.payload["test"] == "redis down"
    finally:
        settings.redis_url = original_redis_url


@pytest.mark.asyncio
async def test_subscriber_in_process(async_session: AsyncSession, event_bus: EventBusService, mission_id: uuid.UUID):
    """
    In-process subscriber for tests/future WS
    """
    received = []

    async def subscriber():
        async for ev in event_bus.subscribe(mission_id):
            received.append(ev)
            if len(received) >= 2:
                break

    # Start subscriber task
    sub_task = asyncio.create_task(subscriber())

    # Give subscriber time to register
    await asyncio.sleep(0.1)

    # Emit events
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_created, source=EventSource.system, mission_id=mission_id, payload={"n": 1}))
    await event_bus.emit(async_session, EventCreate(type=EventType.mission_status_changed, source=EventSource.system, mission_id=mission_id, payload={"n": 2}))

    # Wait for subscriber to receive
    try:
        await asyncio.wait_for(sub_task, timeout=2.0)
    except asyncio.TimeoutError:
        sub_task.cancel()
        pytest.fail("Subscriber did not receive events in time")

    assert len(received) == 2
    assert received[0].payload["n"] == 1
    assert received[1].payload["n"] == 2
