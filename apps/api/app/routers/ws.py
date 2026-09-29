"""
WebSocket Router - Phase 2B-5 Real-Time Runtime Integration - Hardened

Implements:
- WS /api/v1/ws
- Auth handshake: first message {"type":"auth","token":"<NEXUS_DEV_TOKEN>"} -> auth_ok / auth_error
- No token in query/path/logs, constant-time compare
- Lifecycle: CONNECTING -> AUTHENTICATING -> AUTHENTICATED -> SUBSCRIBED -> CLOSED
- Auth timeout, heartbeat/ping, clean disconnect, bounded resources
- Mission subscription with ownership validation and GAP-SAFE replay via EventBus
- Typed protocol errors, no stack traces
- Security: no token logging, ownership enforcement, event scoping, no cross-mission leak

Gap-safe replay/live handoff (hardened):
- Establish live subscription BEFORE replay query
- Start per-connection replay buffer to capture live events during replay
- Query historical events after last_event_id
- Send subscribed ack + replay events
- Drain buffered live events in deterministic order, deduplicate against replayed IDs
- End buffer, resume direct live delivery
- Prevents race where event emitted between replay query and subscription is lost

Limits (MVP):
- MAX_MESSAGE_SIZE 32KB
- AUTH_TIMEOUT 10s
- MAX_SUBS_PER_SOCKET 10
- MAX_CONNECTIONS_PER_PROCESS 100 (enforced in manager)
- MAX_REPLAY_BATCH 100
- REPLAY_BUFFER_MAX 200
"""

import asyncio
import json
import uuid
import logging
from typing import Optional, List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.services.websocket_manager import (
    websocket_manager,
    WSConnectionState,
    MAX_MESSAGE_SIZE_BYTES,
    AUTH_TIMEOUT_SECONDS,
    MAX_SUBSCRIPTIONS_PER_SOCKET,
    MAX_REPLAY_BATCH,
)
from app.services.mission import mission_service
from app.services.event_bus import event_bus_service
from app.core.exceptions import MissionNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()

# Auth error codes - deterministic
AUTH_CODE_MISSING_TOKEN = "auth_missing_token"
AUTH_CODE_INVALID_TOKEN = "auth_invalid_token"
AUTH_CODE_TIMEOUT = "auth_timeout"
AUTH_CODE_TOO_MANY_CONNECTIONS = "too_many_connections"

PROTOCOL_CODE_INVALID_JSON = "invalid_json"
PROTOCOL_CODE_INVALID_TYPE = "invalid_message_type"
PROTOCOL_CODE_NOT_AUTHENTICATED = "not_authenticated"
PROTOCOL_CODE_INVALID_MISSION_ID = "invalid_mission_id"
PROTOCOL_CODE_MISSION_NOT_FOUND = "mission_not_found"
PROTOCOL_CODE_UNAUTHORIZED = "unauthorized"
PROTOCOL_CODE_INVALID_LAST_EVENT_ID = "invalid_last_event_id"
PROTOCOL_CODE_LAST_EVENT_WRONG_MISSION = "last_event_wrong_mission"
PROTOCOL_CODE_OVERSIZED = "message_too_large"
PROTOCOL_CODE_TOO_MANY_SUBS = "too_many_subscriptions"
PROTOCOL_CODE_UNKNOWN = "unknown_error"


def _is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except Exception:
        return False


async def _send_error(websocket: WebSocket, code: str, message: str):
    try:
        await websocket.send_text(json.dumps({"type": "error", "code": code, "message": message}))
    except Exception:
        pass


async def _send_auth_error(websocket: WebSocket, code: str, message: str):
    try:
        await websocket.send_text(json.dumps({"type": "auth_error", "code": code, "message": message}))
    except Exception:
        pass


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session: AsyncSession = Depends(get_db)):
    """
    WS /api/v1/ws
    - Accept
    - Auth handshake with timeout
    - Parse typed client messages
    - Subscribe/unsubscribe with gap-safe replay
    - Forward events via manager broadcast
    - Clean close, no stack traces, no token logging
    """
    await websocket.accept()

    conn = await websocket_manager.register(websocket)
    if conn is None:
        await _send_auth_error(websocket, AUTH_CODE_TOO_MANY_CONNECTIONS, "Too many connections")
        try:
            await websocket.close(code=1013)
        except Exception:
            pass
        return

    conn_id = conn.id

    try:
        try:
            await websocket.send_text(json.dumps({"type": "welcome", "message": "NEXUS WS - send auth first", "version": 1}))
        except Exception:
            await websocket_manager.disconnect(conn_id)
            return

        await websocket_manager.set_authenticating(conn_id)

        authenticated_user_id: Optional[uuid.UUID] = None

        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await _send_auth_error(websocket, AUTH_CODE_TIMEOUT, f"Authentication timeout after {AUTH_TIMEOUT_SECONDS}s")
            try:
                await websocket.close(code=1008)
            except Exception:
                pass
            await websocket_manager.disconnect(conn_id)
            return
        except WebSocketDisconnect:
            await websocket_manager.disconnect(conn_id)
            return
        except Exception:
            await websocket_manager.disconnect(conn_id)
            return

        if len(raw.encode("utf-8")) > MAX_MESSAGE_SIZE_BYTES:
            await _send_error(websocket, PROTOCOL_CODE_OVERSIZED, "Message too large")
            await websocket_manager.disconnect(conn_id)
            try:
                await websocket.close(code=1009)
            except Exception:
                pass
            return

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await _send_error(websocket, PROTOCOL_CODE_INVALID_JSON, "Invalid JSON")
            await websocket_manager.disconnect(conn_id)
            try:
                await websocket.close(code=1003)
            except Exception:
                pass
            return

        if not isinstance(msg, dict) or msg.get("type") != "auth":
            await _send_auth_error(websocket, AUTH_CODE_MISSING_TOKEN, "First message must be auth")
            await websocket_manager.disconnect(conn_id)
            try:
                await websocket.close(code=1008)
            except Exception:
                pass
            return

        token = msg.get("token")
        if not token or not isinstance(token, str) or not token.strip():
            await _send_auth_error(websocket, AUTH_CODE_MISSING_TOKEN, "Missing token")
            await websocket_manager.disconnect(conn_id)
            try:
                await websocket.close(code=1008)
            except Exception:
                pass
            return

        expected = settings.nexus_dev_token
        if not websocket_manager.constant_time_compare(token.strip(), expected):
            logger.info(f"WS auth failed for {conn_id}")
            await _send_auth_error(websocket, AUTH_CODE_INVALID_TOKEN, "Invalid token")
            await websocket_manager.disconnect(conn_id)
            try:
                await websocket.close(code=1008)
            except Exception:
                pass
            return

        try:
            dev_user_id = uuid.uuid5(uuid.NAMESPACE_DNS, "dev-user-nexus")
        except Exception:
            dev_user_id = uuid.uuid4()

        authenticated_user_id = dev_user_id
        await websocket_manager.set_authenticated(conn_id, authenticated_user_id)

        try:
            await websocket.send_text(json.dumps({"type": "auth_ok"}))
        except Exception:
            await websocket_manager.disconnect(conn_id)
            return

        logger.info(f"WS auth_ok {conn_id}")

        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                break

            if len(raw.encode("utf-8")) > MAX_MESSAGE_SIZE_BYTES:
                await _send_error(websocket, PROTOCOL_CODE_OVERSIZED, "Message too large")
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(websocket, PROTOCOL_CODE_INVALID_JSON, "Invalid JSON")
                continue

            if not isinstance(msg, dict):
                await _send_error(websocket, PROTOCOL_CODE_INVALID_TYPE, "Message must be object")
                continue

            mtype = msg.get("type")

            if mtype == "ping":
                try:
                    await websocket.send_text(json.dumps({"type": "pong"}))
                except Exception:
                    break
                continue

            if mtype == "auth":
                try:
                    await websocket.send_text(json.dumps({"type": "auth_ok"}))
                except Exception:
                    break
                continue

            if mtype == "subscribe":
                conn_obj = await websocket_manager.get_connection(conn_id)
                if not conn_obj or not conn_obj.is_authenticated():
                    await _send_error(websocket, PROTOCOL_CODE_NOT_AUTHENTICATED, "Not authenticated")
                    continue

                mission_id_raw = msg.get("mission_id")
                if not mission_id_raw or not _is_valid_uuid(str(mission_id_raw)):
                    await _send_error(websocket, PROTOCOL_CODE_INVALID_MISSION_ID, "Invalid mission_id")
                    continue

                try:
                    mission_id = uuid.UUID(str(mission_id_raw))
                except Exception:
                    await _send_error(websocket, PROTOCOL_CODE_INVALID_MISSION_ID, "Invalid mission_id")
                    continue

                last_event_id_raw = msg.get("last_event_id")
                last_event_id: Optional[uuid.UUID] = None
                if last_event_id_raw is not None:
                    if not _is_valid_uuid(str(last_event_id_raw)):
                        await _send_error(websocket, PROTOCOL_CODE_INVALID_LAST_EVENT_ID, "Invalid last_event_id")
                        continue
                    try:
                        last_event_id = uuid.UUID(str(last_event_id_raw))
                    except Exception:
                        await _send_error(websocket, PROTOCOL_CODE_INVALID_LAST_EVENT_ID, "Invalid last_event_id")
                        continue

                try:
                    mission = await mission_service.get_mission(session, mission_id)
                except MissionNotFoundError:
                    await _send_error(websocket, PROTOCOL_CODE_MISSION_NOT_FOUND, "Mission not found")
                    continue
                except Exception as e:
                    logger.warning(f"WS mission lookup failed {mission_id}: {e}")
                    await _send_error(websocket, PROTOCOL_CODE_MISSION_NOT_FOUND, "Mission not found")
                    continue

                if mission.user_id is not None:
                    if str(mission.user_id) != str(authenticated_user_id):
                        await _send_error(websocket, PROTOCOL_CODE_UNAUTHORIZED, "Unauthorized for mission")
                        continue

                if last_event_id is not None:
                    try:
                        from sqlalchemy import select
                        from app.models.event import Event

                        q = select(Event).where(Event.id == last_event_id)
                        res = await session.execute(q)
                        last_event = res.scalar_one_or_none()
                        if last_event is None:
                            await _send_error(websocket, PROTOCOL_CODE_INVALID_LAST_EVENT_ID, "last_event_id not found")
                            continue
                        if last_event.mission_id != mission_id:
                            await _send_error(websocket, PROTOCOL_CODE_LAST_EVENT_WRONG_MISSION, "last_event_id belongs to different mission")
                            continue
                    except Exception as e:
                        logger.warning(f"WS last_event_id check failed: {e}")
                        await _send_error(websocket, PROTOCOL_CODE_INVALID_LAST_EVENT_ID, "Invalid last_event_id")
                        continue

                conn_obj = await websocket_manager.get_connection(conn_id)
                if conn_obj and len(conn_obj.subscriptions) >= MAX_SUBSCRIPTIONS_PER_SOCKET:
                    await _send_error(websocket, PROTOCOL_CODE_TOO_MANY_SUBS, f"Too many subscriptions max {MAX_SUBSCRIPTIONS_PER_SOCKET}")
                    continue

                # --- GAP-SAFE REPLAY/LIVE HANDOFF ---
                # 1. Establish live subscription BEFORE replay query to avoid race
                # 2. Start buffering live events during replay
                # 3. Query historical events after last_event_id
                # 4. Send subscribed ack + replay
                # 5. Drain buffered live events deduplicated, sorted deterministically
                # 6. End buffer, resume direct live delivery

                # Step 1: Add subscription first (live)
                added = await websocket_manager.add_subscription(conn_id, mission_id, last_event_id)
                if not added:
                    await _send_error(websocket, PROTOCOL_CODE_TOO_MANY_SUBS, "Too many subscriptions")
                    continue

                # Step 2: Start buffering live events that arrive during replay query
                await websocket_manager.start_replay_buffer(conn_id, mission_id)

                # Step 3: Query historical replay events (gap-safe: subscription already active, so events after this point will be buffered)
                replay_events = []
                try:
                    events, total = await event_bus_service.list(
                        session=session,
                        mission_id=mission_id,
                        last_event_id=last_event_id,
                        limit=MAX_REPLAY_BATCH,
                        offset=0,
                    )
                    replay_events = events
                except Exception as e:
                    logger.warning(f"WS replay list failed for {mission_id}: {e}")
                    replay_events = []

                # Step 4: Send subscribed ack
                try:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "subscribed",
                                "mission_id": str(mission_id),
                                "last_event_id": str(last_event_id) if last_event_id else None,
                                "replay_count": len(replay_events),
                            }
                        )
                    )
                except Exception:
                    await websocket_manager.remove_subscription(conn_id, mission_id)
                    await websocket_manager.end_replay_buffer(conn_id, mission_id)
                    break

                # Step 5: Send replay events in deterministic order
                replayed_ids: Set[uuid.UUID] = set()
                for ev in replay_events:
                    try:
                        envelope = {
                            "id": str(ev.id),
                            "type": ev.type,
                            "source": ev.source,
                            "mission_id": str(ev.mission_id),
                            "task_id": str(ev.task_id) if ev.task_id else None,
                            "agent_id": str(ev.agent_id) if ev.agent_id else None,
                            "timestamp": ev.timestamp.isoformat(),
                            "version": ev.version,
                            "payload": ev.payload,
                            "metadata": ev.metadata_,
                        }
                        await websocket.send_text(json.dumps(envelope))
                        replayed_ids.add(ev.id)
                        async with websocket_manager._lock:
                            c = websocket_manager._connections.get(conn_id)
                            if c:
                                c.last_event_ids[mission_id] = ev.id
                    except Exception:
                        break

                # Step 6: Drain buffered live events that arrived during replay query/send
                # Deduplicate against replayed_ids and sort deterministically by timestamp ASC, id ASC
                try:
                    buffered = await websocket_manager.end_replay_buffer(conn_id, mission_id)
                    # Deduplicate
                    deduped = []
                    seen = set(replayed_ids)
                    for b_ev in buffered:
                        try:
                            b_id = getattr(b_ev, "id", None)
                            if b_id is None and isinstance(b_ev, dict):
                                b_id = b_ev.get("id")
                            if b_id:
                                b_uuid = uuid.UUID(str(b_id)) if not isinstance(b_id, uuid.UUID) else b_id
                                if b_uuid in seen:
                                    continue
                                seen.add(b_uuid)
                            deduped.append(b_ev)
                        except Exception:
                            deduped.append(b_ev)

                    # Sort deterministically by timestamp + id if possible
                    def _sort_key(e):
                        try:
                            ts = getattr(e, "timestamp", None)
                            if ts is None and isinstance(e, dict):
                                ts = e.get("timestamp")
                            if hasattr(ts, "isoformat"):
                                ts_str = ts.isoformat()
                            else:
                                ts_str = str(ts) if ts else ""
                            eid = getattr(e, "id", "")
                            if isinstance(e, dict):
                                eid = e.get("id", "")
                            return (ts_str, str(eid))
                        except Exception:
                            return ("", "")

                    deduped.sort(key=_sort_key)

                    for b_ev in deduped:
                        try:
                            # Serialize using manager's serializer
                            envelope = websocket_manager._serialize_event(b_ev)
                            await websocket.send_text(json.dumps(envelope))
                            async with websocket_manager._lock:
                                c = websocket_manager._connections.get(conn_id)
                                if c:
                                    try:
                                        eid = getattr(b_ev, "id", None)
                                        if eid is None and isinstance(b_ev, dict):
                                            eid = b_ev.get("id")
                                        if eid:
                                            eid_uuid = uuid.UUID(str(eid)) if not isinstance(eid, uuid.UUID) else eid
                                            c.last_event_ids[mission_id] = eid_uuid
                                    except Exception:
                                        pass
                        except Exception:
                            break
                except Exception as e:
                    logger.warning(f"WS buffer drain failed for {conn_id} {mission_id}: {e}")
                    # Ensure buffer ended even on failure
                    try:
                        await websocket_manager.end_replay_buffer(conn_id, mission_id)
                    except Exception:
                        pass

                continue

            if mtype == "unsubscribe":
                mission_id_raw = msg.get("mission_id")
                if not mission_id_raw or not _is_valid_uuid(str(mission_id_raw)):
                    await _send_error(websocket, PROTOCOL_CODE_INVALID_MISSION_ID, "Invalid mission_id")
                    continue
                try:
                    mission_id = uuid.UUID(str(mission_id_raw))
                except Exception:
                    await _send_error(websocket, PROTOCOL_CODE_INVALID_MISSION_ID, "Invalid mission_id")
                    continue

                await websocket_manager.remove_subscription(conn_id, mission_id)
                # Also clear any replay buffer
                try:
                    await websocket_manager.end_replay_buffer(conn_id, mission_id)
                except Exception:
                    pass
                try:
                    await websocket.send_text(json.dumps({"type": "unsubscribed", "mission_id": str(mission_id)}))
                except Exception:
                    break
                continue

            await _send_error(websocket, PROTOCOL_CODE_INVALID_TYPE, f"Unknown message type: {mtype}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WS error {conn_id}: {e}")
    finally:
        await websocket_manager.disconnect(conn_id)
        try:
            await websocket.close()
        except Exception:
            pass
