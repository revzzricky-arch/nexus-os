"""
WebSocket Manager - Phase 2B-5 Real-Time Runtime Integration

Responsibilities:
- Connection registration
- Auth state tracking
- Mission subscriptions
- broadcast_event with gap-safe replay buffering
- disconnect / cleanup
- Bounded tracking

No complex business logic, no MCP, no shell
Security: no token logging, constant-time compare, ownership enforcement via caller, event scoping

Limits (MVP documented):
- MAX_CONNECTIONS_PER_PROCESS = 100
- MAX_SUBSCRIPTIONS_PER_SOCKET = 10
- MAX_MESSAGE_SIZE = 32KB
- AUTH_TIMEOUT_SECONDS = 10
- MAX_REPLAY_BATCH = 100
- HEARTBEAT_INTERVAL = 30s (client ping, server pong)
- REPLAY_BUFFER_MAX = 200 (buffer live events during replay phase)

Gap-safe replay/live handoff:
- Subscription is established BEFORE replay query
- Live events arriving during replay query are buffered per-connection per-mission
- Replay sends historical events up to subscription point
- Buffered live events are then drained in deterministic order, deduplicated against replayed IDs
- After buffer drain, live delivery resumes directly
- Prevents race where event emitted between replay query and subscription is lost
"""

import asyncio
import uuid
import hmac
import json
from typing import Dict, Set, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# MVP Limits - documented in ADR
MAX_CONNECTIONS_PER_PROCESS = 100
MAX_SUBSCRIPTIONS_PER_SOCKET = 10
MAX_MESSAGE_SIZE_BYTES = 32 * 1024  # 32KB
AUTH_TIMEOUT_SECONDS = 10
MAX_REPLAY_BATCH = 100
HEARTBEAT_INTERVAL_SECONDS = 30
REPLAY_BUFFER_MAX = 200


class WSConnectionState(str, Enum):
    CONNECTING = "CONNECTING"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    SUBSCRIBED = "SUBSCRIBED"
    CLOSED = "CLOSED"


@dataclass
class WSConnection:
    id: str
    websocket: Any  # FastAPI WebSocket
    state: WSConnectionState = WSConnectionState.CONNECTING
    authenticated_user_id: Optional[uuid.UUID] = None
    authenticated_at: Optional[datetime] = None
    subscriptions: Set[uuid.UUID] = field(default_factory=set)
    last_event_ids: Dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # For bounded tracking, count messages
    message_count: int = 0
    # Gap-safe replay buffering
    replay_buffers: Dict[uuid.UUID, List[Any]] = field(default_factory=dict)
    replay_in_progress: Set[uuid.UUID] = field(default_factory=set)

    def is_authenticated(self) -> bool:
        return self.state in (WSConnectionState.AUTHENTICATED, WSConnectionState.SUBSCRIBED) and self.authenticated_user_id is not None


class WebSocketManager:
    """
    In-process WebSocket manager
    Redis NOT required - Postgres is source of truth, in-process subs acceptable
    Optionally future Redis adapter can be isolated behind this boundary
    Implements gap-safe replay/live handoff via per-connection buffering
    """

    def __init__(self):
        self._connections: Dict[str, WSConnection] = {}
        self._lock = asyncio.Lock()
        # mission_id -> set(connection_id)
        self._mission_subscribers: Dict[uuid.UUID, Set[str]] = {}

    async def register(self, websocket: Any) -> Optional[WSConnection]:
        """
        Register new connection, bounded by MAX_CONNECTIONS_PER_PROCESS
        Returns connection or None if limit exceeded
        """
        async with self._lock:
            if len(self._connections) >= MAX_CONNECTIONS_PER_PROCESS:
                logger.warning(f"WS connection limit reached: {len(self._connections)}")
                return None

            conn_id = str(uuid.uuid4())
            conn = WSConnection(
                id=conn_id,
                websocket=websocket,
                state=WSConnectionState.CONNECTING,
            )
            self._connections[conn_id] = conn
            logger.info(f"WS registered {conn_id}, total={len(self._connections)}")
            return conn

    async def set_authenticating(self, conn_id: str):
        async with self._lock:
            conn = self._connections.get(conn_id)
            if conn:
                conn.state = WSConnectionState.AUTHENTICATING

    async def set_authenticated(self, conn_id: str, user_id: uuid.UUID):
        async with self._lock:
            conn = self._connections.get(conn_id)
            if conn:
                conn.state = WSConnectionState.AUTHENTICATED
                conn.authenticated_user_id = user_id
                conn.authenticated_at = datetime.now(timezone.utc)

    async def add_subscription(self, conn_id: str, mission_id: uuid.UUID, last_event_id: Optional[uuid.UUID] = None) -> bool:
        """
        Add mission subscription, bounded by MAX_SUBSCRIPTIONS_PER_SOCKET
        Returns True if added, False if limit exceeded
        """
        async with self._lock:
            conn = self._connections.get(conn_id)
            if not conn:
                return False
            if len(conn.subscriptions) >= MAX_SUBSCRIPTIONS_PER_SOCKET:
                return False

            conn.subscriptions.add(mission_id)
            if last_event_id:
                conn.last_event_ids[mission_id] = last_event_id

            # Update reverse index
            if mission_id not in self._mission_subscribers:
                self._mission_subscribers[mission_id] = set()
            self._mission_subscribers[mission_id].add(conn_id)

            # Update state to SUBSCRIBED if at least one sub
            if conn.subscriptions:
                conn.state = WSConnectionState.SUBSCRIBED

            return True

    async def remove_subscription(self, conn_id: str, mission_id: uuid.UUID):
        async with self._lock:
            conn = self._connections.get(conn_id)
            if conn:
                conn.subscriptions.discard(mission_id)
                conn.last_event_ids.pop(mission_id, None)
                conn.replay_buffers.pop(mission_id, None)
                conn.replay_in_progress.discard(mission_id)
                if not conn.subscriptions and conn.state == WSConnectionState.SUBSCRIBED:
                    conn.state = WSConnectionState.AUTHENTICATED

            # Update reverse index
            if mission_id in self._mission_subscribers:
                self._mission_subscribers[mission_id].discard(conn_id)
                if not self._mission_subscribers[mission_id]:
                    del self._mission_subscribers[mission_id]

    async def disconnect(self, conn_id: str):
        """
        Clean disconnect, remove from all tracking
        """
        async with self._lock:
            conn = self._connections.pop(conn_id, None)
            if not conn:
                return

            # Remove from mission subscribers
            for mission_id in list(conn.subscriptions):
                if mission_id in self._mission_subscribers:
                    self._mission_subscribers[mission_id].discard(conn_id)
                    if not self._mission_subscribers[mission_id]:
                        del self._mission_subscribers[mission_id]

            conn.state = WSConnectionState.CLOSED
            logger.info(f"WS disconnected {conn_id}, remaining={len(self._connections)}")

    async def get_connection(self, conn_id: str) -> Optional[WSConnection]:
        async with self._lock:
            return self._connections.get(conn_id)

    async def get_connections_for_mission(self, mission_id: uuid.UUID) -> List[WSConnection]:
        async with self._lock:
            conn_ids = self._mission_subscribers.get(mission_id, set()).copy()
            conns = []
            for cid in conn_ids:
                c = self._connections.get(cid)
                if c and c.is_authenticated():
                    conns.append(c)
            return conns

    # --- Gap-safe replay buffering ---

    async def start_replay_buffer(self, conn_id: str, mission_id: uuid.UUID):
        """
        Start buffering live events for this connection+mission during replay phase
        Must be called AFTER add_subscription and BEFORE replay query
        """
        async with self._lock:
            conn = self._connections.get(conn_id)
            if not conn:
                return
            conn.replay_in_progress.add(mission_id)
            if mission_id not in conn.replay_buffers:
                conn.replay_buffers[mission_id] = []

    async def end_replay_buffer(self, conn_id: str, mission_id: uuid.UUID) -> List[Any]:
        """
        End buffering and return buffered events
        Future live events will be sent directly
        Returns list of buffered events in arrival order
        """
        async with self._lock:
            conn = self._connections.get(conn_id)
            if not conn:
                return []
            buffered = conn.replay_buffers.pop(mission_id, [])
            conn.replay_in_progress.discard(mission_id)
            return buffered

    async def get_buffered_count(self, conn_id: str, mission_id: uuid.UUID) -> int:
        async with self._lock:
            conn = self._connections.get(conn_id)
            if not conn:
                return 0
            return len(conn.replay_buffers.get(mission_id, []))

    async def broadcast_event(self, event: Any):
        """
        Broadcast EventEnvelope to all subscribed connections for event.mission_id
        Handles gap-safe buffering: if replay_in_progress for conn+mission, buffer instead of direct send
        Handles disconnected clients gracefully, no crash
        """
        mission_id = getattr(event, "mission_id", None)
        if mission_id is None:
            if isinstance(event, dict):
                mid = event.get("mission_id")
                if mid:
                    try:
                        mission_id = uuid.UUID(str(mid)) if not isinstance(mid, uuid.UUID) else mid
                    except Exception:
                        return
            else:
                return

        if isinstance(mission_id, str):
            try:
                mission_id = uuid.UUID(mission_id)
            except Exception:
                return

        # Get subscribers snapshot
        conns = await self.get_connections_for_mission(mission_id)

        if not conns:
            return

        # Serialize event once
        envelope = self._serialize_event(event)

        # Send to each, with buffering check
        for conn in conns:
            try:
                # Check if replay in progress for this conn+mission - buffer instead of direct send
                should_buffer = False
                async with self._lock:
                    tracked = self._connections.get(conn.id)
                    if tracked and mission_id in tracked.replay_in_progress:
                        # Buffer live event during replay phase
                        buf = tracked.replay_buffers.get(mission_id)
                        if buf is None:
                            tracked.replay_buffers[mission_id] = []
                            buf = tracked.replay_buffers[mission_id]
                        # Bounded buffer
                        if len(buf) < REPLAY_BUFFER_MAX:
                            buf.append(event)
                        else:
                            # Drop oldest if overflow to keep bounded
                            buf.pop(0)
                            buf.append(event)
                        should_buffer = True

                if should_buffer:
                    continue

                # Normal live delivery - update last_event_id tracking and send
                async with self._lock:
                    tracked = self._connections.get(conn.id)
                    if tracked:
                        try:
                            eid = getattr(event, "id", None)
                            if eid is None and isinstance(event, dict):
                                eid = event.get("id")
                            if eid:
                                eid_uuid = uuid.UUID(str(eid)) if not isinstance(eid, uuid.UUID) else eid
                                tracked.last_event_ids[mission_id] = eid_uuid
                        except Exception:
                            pass

                await conn.websocket.send_text(json.dumps(envelope))
            except Exception as e:
                logger.debug(f"WS broadcast failed for {conn.id}: {e}")
                continue

    def _serialize_event(self, event: Any) -> Dict[str, Any]:
        """
        Serialize Event model to EventEnvelope dict
        Uses existing envelope shape
        """
        if isinstance(event, dict):
            return event

        try:
            return {
                "id": str(event.id),
                "type": event.type,
                "source": event.source,
                "mission_id": str(event.mission_id),
                "task_id": str(event.task_id) if getattr(event, "task_id", None) else None,
                "agent_id": str(event.agent_id) if getattr(event, "agent_id", None) else None,
                "timestamp": event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp),
                "version": getattr(event, "version", 1),
                "payload": getattr(event, "payload", {}),
                "metadata": getattr(event, "metadata_", None) or getattr(event, "metadata", None),
            }
        except Exception:
            return {
                "id": str(getattr(event, "id", uuid.uuid4())),
                "type": str(getattr(event, "type", "unknown")),
                "mission_id": str(getattr(event, "mission_id", "")),
                "payload": {},
            }

    async def count_connections(self) -> int:
        async with self._lock:
            return len(self._connections)

    async def cleanup(self):
        async with self._lock:
            self._connections.clear()
            self._mission_subscribers.clear()

    def constant_time_compare(self, a: str, b: str) -> bool:
        try:
            return hmac.compare_digest(a, b)
        except Exception:
            return False


# Singleton for process
websocket_manager = WebSocketManager()
