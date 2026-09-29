"""
EventBus Service - Phase 2B-2 Mission API + EventBus Foundation

Source of truth: Postgres events table
Optional realtime layer: Redis behind clean abstraction, NOT authoritative
If Redis unavailable, DB persistence continues working - do not lose events

Implements:
- emit(event) -> persists to Postgres, optional Redis publish
- list(...) -> deterministic ordering, mission scoping mandatory, filters, pagination, last_event_id replay
- subscribe(...) -> in-process async subscriber mechanism for tests/future WS

EventEnvelope per shared contract:
id, type, source, mission_id, task_id nullable, agent_id nullable, timestamp, version, payload, metadata

Event types required now: mission_created, mission_status_changed
Prepared for later: task_status_changed, agent_state_changed, tool_call_started, tool_call_completed, tool_call_failed, approval_requested, approval_decided, handoff, error, cost_updated
"""

import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.event import Event
from app.schemas.event import EventCreate, EventType, EventSource
from app.config import settings

# In-process subscriber registry for tests/future WS (MVP)
# Keeps Redis optional and isolated
_subscribers: Dict[str, List[asyncio.Queue]] = {}


def _get_subscriber_key(mission_id: uuid.UUID) -> str:
    return f"mission:{mission_id}"


class EventBusService:
    """
    EventBus with Postgres as authoritative source
    Optional Redis layer isolated - does NOT become authoritative
    """

    async def emit(
        self,
        session: AsyncSession,
        event_create: EventCreate,
    ) -> Event:
        """
        Persist event to Postgres (source of truth)
        Optional Redis publish behind abstraction - does not affect DB persistence
        """
        # Create EventEnvelope matching shared contract
        event = Event(
            id=uuid.uuid4(),
            type=event_create.type.value if isinstance(event_create.type, EventType) else event_create.type,
            source=event_create.source.value if isinstance(event_create.source, EventSource) else event_create.source,
            mission_id=event_create.mission_id,
            task_id=event_create.task_id,
            agent_id=event_create.agent_id,
            agent_run_id=event_create.agent_run_id,
            timestamp=datetime.now(timezone.utc),
            version=event_create.version,
            payload=event_create.payload,
            metadata_=event_create.metadata,
        )

        session.add(event)
        await session.flush()
        await session.refresh(event)

        # Optional Redis publish - isolated, failures do not prevent DB persistence
        # For MVP, we attempt Redis but swallow errors to ensure DB is source of truth
        try:
            await self._publish_redis(event)
        except Exception:
            # Do not lose events because Redis unavailable - DB already persisted
            pass

        # In-process publish for tests/future WS
        await self._publish_in_process(event)

        return event

    async def _publish_redis(self, event: Event) -> None:
        """
        Optional Redis publish - isolated abstraction
        If Redis unavailable, this is no-op (DB remains source of truth)
        """
        # Check if redis feature enabled and redis_url configured
        # We do not require redis package to be installed for Phase 2B-2
        # Import lazily to keep Redis optional
        if not settings.redis_url:
            return

        try:
            import redis.asyncio as redis  # type: ignore

            # Create short-lived client for publish (MVP-only, isolated behind service boundary)
            # Note: This asyncio client usage is MVP-only and isolated so it can be replaced by durable worker/queue later per correction
            client = redis.from_url(settings.redis_url, decode_responses=True)
            channel = f"mission:{event.mission_id}:events:pubsub"
            # Publish event envelope JSON
            import json

            envelope = {
                "id": str(event.id),
                "type": event.type,
                "source": event.source,
                "mission_id": str(event.mission_id),
                "task_id": str(event.task_id) if event.task_id else None,
                "agent_id": str(event.agent_id) if event.agent_id else None,
                "agent_run_id": str(event.agent_run_id) if event.agent_run_id else None,
                "timestamp": event.timestamp.isoformat(),
                "version": event.version,
                "payload": event.payload,
                "metadata": event.metadata_,
            }
            await client.publish(channel, json.dumps(envelope))
            # Also XADD to stream for durable replay if needed (optional)
            stream_key = f"mission:{event.mission_id}:events:stream"
            try:
                await client.xadd(stream_key, {"data": json.dumps(envelope)}, maxlen=10000)
            except Exception:
                pass  # Stream optional

            await client.aclose()
        except ImportError:
            # Redis package not installed - optional, DB remains source
            return
        except Exception:
            # Redis unavailable - DB already persisted, do not lose events
            return

    async def _publish_in_process(self, event: Event) -> None:
        """In-process async subscriber mechanism for tests/future WS"""
        key = _get_subscriber_key(event.mission_id)
        queues = _subscribers.get(key, [])
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def list(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
        event_type: Optional[str] = None,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        last_event_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[Event], int]:
        """
        List events for mission with deterministic ordering and mission scoping mandatory
        Supports filters: type, from/to timestamp, last_event_id replay, pagination
        Deterministic ordering: timestamp ASC + id ASC
        Safety: if last_event_id doesn't belong to requested mission, handle safely rather than leaking data
        """
        # Base query scoped to mission_id (mandatory)
        base_query = select(Event).where(Event.mission_id == mission_id)

        # Type filter
        if event_type:
            base_query = base_query.where(Event.type == event_type)

        # Timestamp filters
        if from_timestamp:
            base_query = base_query.where(Event.timestamp >= from_timestamp)
        if to_timestamp:
            base_query = base_query.where(Event.timestamp <= to_timestamp)

        # last_event_id replay: return events after last_event_id for this mission only
        # Safety: check if last_event_id belongs to requested mission, if not, handle safely (return empty or from start, not leaking)
        if last_event_id:
            # First, check if last_event_id exists and belongs to mission
            last_event_query = select(Event).where(Event.id == last_event_id)
            result = await session.execute(last_event_query)
            last_event = result.scalar_one_or_none()

            if last_event is None:
                # Event not found - return empty list for safety, do not leak
                # Alternatively could return from start, but we choose empty to avoid confusion
                # For replay, if ID not found, we return events from beginning? Let's handle as: if not found, return from start is more useful for reconnect
                # But per requirement: handle safely rather than leaking data
                # We will check: if last_event_id not in mission, do not return unrelated missions' events
                # So we return events after timestamp of last_event_id if we can find it, else from start
                # Since not found, we return from start (still scoped to mission)
                pass
            elif last_event.mission_id != mission_id:
                # last_event_id belongs to different mission - handle safely, do not leak
                # Return empty to avoid leaking data from other mission
                return [], 0
            else:
                # last_event belongs to this mission - return events after its timestamp + id for deterministic ordering
                # Deterministic ordering: timestamp ASC, id ASC
                # So we want events where (timestamp > last_timestamp) OR (timestamp == last_timestamp AND id > last_id)
                base_query = base_query.where(
                    or_(
                        Event.timestamp > last_event.timestamp,
                        and_(Event.timestamp == last_event.timestamp, Event.id > last_event.id),
                    )
                )

        # Count total
        count_query = select(Event).where(Event.mission_id == mission_id)
        if event_type:
            count_query = count_query.where(Event.type == event_type)
        if from_timestamp:
            count_query = count_query.where(Event.timestamp >= from_timestamp)
        if to_timestamp:
            count_query = count_query.where(Event.timestamp <= to_timestamp)
        if last_event_id and last_event and last_event.mission_id == mission_id:
            count_query = count_query.where(
                or_(
                    Event.timestamp > last_event.timestamp,
                    and_(Event.timestamp == last_event.timestamp, Event.id > last_event.id),
                )
            )

        # For total count, we need to count
        from sqlalchemy import func

        total_query = select(func.count()).select_from(count_query.subquery())
        total_result = await session.execute(total_query)
        total = total_result.scalar() or 0

        # Deterministic ordering: timestamp ASC + id ASC
        base_query = base_query.order_by(Event.timestamp.asc(), Event.id.asc())
        base_query = base_query.limit(limit).offset(offset)

        result = await session.execute(base_query)
        events = result.scalars().all()

        return list(events), total

    async def subscribe(self, mission_id: uuid.UUID) -> AsyncGenerator[Event, None]:
        """
        In-process subscriber for tests/future WS
        Yields events as they are emitted for mission_id
        """
        key = _get_subscriber_key(mission_id)
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        if key not in _subscribers:
            _subscribers[key] = []
        _subscribers[key].append(queue)

        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            # Cleanup
            if key in _subscribers:
                try:
                    _subscribers[key].remove(queue)
                except ValueError:
                    pass
                if not _subscribers[key]:
                    del _subscribers[key]


# Singleton
event_bus_service = EventBusService()
