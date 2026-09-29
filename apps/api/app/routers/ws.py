"""
WebSocket Router - Phase 2B-5 Real-Time Runtime Integration

Implements:
- WS /api/v1/ws
- Auth handshake: first message {"type":"auth","token":"<NEXUS_DEV_TOKEN>"} -> auth_ok / auth_error
- No token in query/path/logs, constant-time compare
- Lifecycle: CONNECTING -> AUTHENTICATING -> AUTHENTICATED -> SUBSCRIBED -> CLOSED
- Auth timeout, heartbeat/ping, clean disconnect, bounded resources
- Mission subscription with ownership validation and replay via EventBus
- Typed protocol errors, no stack traces
- Security: no token logging, ownership enforcement, event scoping, no cross-mission leak

Limits (MVP):
- MAX_MESSAGE_SIZE 32KB
- AUTH_TIMEOUT 10s
- MAX_SUBS_PER_SOCKET 10
- MAX_CONNECTIONS_PER_PROCESS 100 (enforced in manager)
- MAX_REPLAY_BATCH 100
"""

import asyncio
import json
import uuid
import logging
from typing import Optional

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
    - Subscribe/unsubscribe with ownership + replay
    - Forward events via manager broadcast
    - Clean close, no stack traces, no token logging
    """
    # Accept connection
    await websocket.accept()

    # Register with bounded tracking
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
        # Send welcome - does not require auth
        try:
            await websocket.send_text(json.dumps({"type": "welcome", "message": "NEXUS WS - send auth first", "version": 1}))
        except Exception:
            await websocket_manager.disconnect(conn_id)
            return

        # Lifecycle: CONNECTING -> AUTHENTICATING with timeout
        await websocket_manager.set_authenticating(conn_id)

        authenticated_user_id: Optional[uuid.UUID] = None

        # Wait for auth message with timeout
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

        # Validate message size
        if len(raw.encode("utf-8")) > MAX_MESSAGE_SIZE_BYTES:
            await _send_error(websocket, PROTOCOL_CODE_OVERSIZED, "Message too large")
            await websocket_manager.disconnect(conn_id)
            try:
                await websocket.close(code=1009)
            except Exception:
                pass
            return

        # Parse JSON
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

        # Must be auth type first
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

        # Constant-time compare, no token logging
        expected = settings.nexus_dev_token
        if not websocket_manager.constant_time_compare(token.strip(), expected):
            # Do not log token
            logger.info(f"WS auth failed for {conn_id}")
            await _send_auth_error(websocket, AUTH_CODE_INVALID_TOKEN, "Invalid token")
            await websocket_manager.disconnect(conn_id)
            try:
                await websocket.close(code=1008)
            except Exception:
                pass
            return

        # Auth success - for MVP, dev user id is deterministic or from settings
        # We use a fixed dev user id for ownership checks: if mission.user_id is None, allow dev user
        # In real auth, we'd decode user from token; here dev token maps to dev user
        # We create a deterministic dev user UUID from token? Use uuid5 for stability
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

        # Main loop: AUTHENTICATED -> SUBSCRIBED
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
                # Already authenticated - idempotent auth_ok
                try:
                    await websocket.send_text(json.dumps({"type": "auth_ok"}))
                except Exception:
                    break
                continue

            if mtype == "subscribe":
                # Validate authenticated
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

                # Validate mission exists and ownership
                try:
                    mission = await mission_service.get_mission(session, mission_id)
                except MissionNotFoundError:
                    await _send_error(websocket, PROTOCOL_CODE_MISSION_NOT_FOUND, "Mission not found")
                    continue
                except Exception as e:
                    logger.warning(f"WS mission lookup failed {mission_id}: {e}")
                    await _send_error(websocket, PROTOCOL_CODE_MISSION_NOT_FOUND, "Mission not found")
                    continue

                # Ownership enforcement: dev-user allow, None owner allow? Actually None owner should be allowed for dev user? Per previous PR, None owner -> PermissionDenied but for WS we allow dev user?
                # Spec: validate authenticated user, mission exists, ownership
                # We implement same as approval: if mission.user_id is None, allow dev user (fail-closed only for non-dev future users)
                # For MVP, dev user is allowed for all, but we check if mission.user_id exists and is not dev user, deny
                # Simplified: if mission.user_id is not None and str(mission.user_id) != str(authenticated_user_id) and str(mission.user_id) != "dev" -> unauthorized
                # Actually previous logic: dev-user allow, anonymous deny, non-dev compared against mission.user_id
                # For WS, authenticated_user_id is dev user, so we allow if mission.user_id is None or matches dev user or is dev-like
                # We'll implement: if mission.user_id is None -> allow dev user (since scaffold missions have no owner)
                # If mission.user_id != dev_user_id and mission.user_id is not None -> check if dev user? For now allow dev user always for MVP to preserve existing tests
                # But we must enforce no cross-mission leak: we will still enforce that dev user is considered owner for None, and for other user_id we deny
                # Let's implement strict: if mission.user_id is not None and str(mission.user_id) != str(authenticated_user_id):
                #   If mission.user_id is not None, deny unless dev user is considered super? For MVP, we allow dev user to access all? That would weaken ownership.
                #   Safer: allow if mission.user_id is None, otherwise require exact match. But then existing scaffold missions with user_id None will be accessible.
                #   For missions with user_id set to other, dev user should be denied to test ownership. So we implement exact match when user_id is not None.
                #   However dev_user_id is deterministic, so if mission was created with dev_user_id, it matches. If mission has random user_id, it will be denied - correct for ownership test.
                if mission.user_id is not None:
                    if str(mission.user_id) != str(authenticated_user_id):
                        # Check if dev user should be allowed for all in dev mode? For security, we enforce ownership
                        # But we need to allow missions created without user_id (None) to be accessible
                        # So for non-None mismatch, deny
                        await _send_error(websocket, PROTOCOL_CODE_UNAUTHORIZED, "Unauthorized for mission")
                        continue

                # Validate last_event_id belongs to same mission if supplied
                if last_event_id is not None:
                    try:
                        # Use event_bus list to check existence? We can query event directly
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

                # Check subscription limit
                conn_obj = await websocket_manager.get_connection(conn_id)
                if conn_obj and len(conn_obj.subscriptions) >= MAX_SUBSCRIPTIONS_PER_SOCKET:
                    await _send_error(websocket, PROTOCOL_CODE_TOO_MANY_SUBS, f"Too many subscriptions max {MAX_SUBSCRIPTIONS_PER_SOCKET}")
                    continue

                # Replay missed events from Postgres via EventBus
                # Load historical after last_event_id deterministic order, bounded batch
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

                # Register live subscription BEFORE sending replay to avoid gap?
                # To avoid duplicate at boundary, we register first, then send replay, and ensure broadcast does not duplicate replayed events
                # Our replay is up to now, live events after now will be broadcast via manager
                # To avoid duplicate, we track last_event_id and ensure broadcast updates last_event_id
                added = await websocket_manager.add_subscription(conn_id, mission_id, last_event_id)
                if not added:
                    await _send_error(websocket, PROTOCOL_CODE_TOO_MANY_SUBS, "Too many subscriptions")
                    continue

                # Send subscribed ack
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
                    break

                # Send replay events in deterministic order (timestamp ASC, id ASC) - already ordered by list
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
                        # Update last_event_id tracking to avoid duplicate at boundary
                        async with websocket_manager._lock:
                            c = websocket_manager._connections.get(conn_id)
                            if c:
                                c.last_event_ids[mission_id] = ev.id
                    except Exception:
                        # If send fails, break replay but keep subscription? We'll break loop
                        break

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
                try:
                    await websocket.send_text(json.dumps({"type": "unsubscribed", "mission_id": str(mission_id)}))
                except Exception:
                    break
                continue

            # Unknown type
            await _send_error(websocket, PROTOCOL_CODE_INVALID_TYPE, f"Unknown message type: {mtype}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        # No stack traces to client, log internally
        logger.warning(f"WS error {conn_id}: {e}")
    finally:
        await websocket_manager.disconnect(conn_id)
        try:
            await websocket.close()
        except Exception:
            pass
