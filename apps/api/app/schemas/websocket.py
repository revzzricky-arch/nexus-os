"""
WebSocket Protocol - Phase 2B-5 Real-Time Runtime Integration

Separate protocol definition from EventEnvelope (authoritative shared/src/events.ts)
Do not change existing EventEnvelope semantics
"""

from typing import Optional, Literal, Union, Any, Dict
from pydantic import BaseModel, Field
import uuid


# Client -> Server messages
class WSClientAuth(BaseModel):
    type: Literal["auth"] = "auth"
    token: str = Field(..., description="NEXUS_DEV_TOKEN, not in URL")


class WSClientSubscribe(BaseModel):
    type: Literal["subscribe"] = "subscribe"
    mission_id: uuid.UUID
    last_event_id: Optional[uuid.UUID] = None


class WSClientUnsubscribe(BaseModel):
    type: Literal["unsubscribe"] = "unsubscribe"
    mission_id: uuid.UUID


class WSClientPing(BaseModel):
    type: Literal["ping"] = "ping"


# Server -> Client messages
class WSServerAuthOk(BaseModel):
    type: Literal["auth_ok"] = "auth_ok"


class WSServerAuthError(BaseModel):
    type: Literal["auth_error"] = "auth_error"
    code: str
    message: str


class WSServerSubscribed(BaseModel):
    type: Literal["subscribed"] = "subscribed"
    mission_id: uuid.UUID
    last_event_id: Optional[uuid.UUID] = None
    replay_count: int = 0


class WSServerUnsubscribed(BaseModel):
    type: Literal["unsubscribed"] = "unsubscribed"
    mission_id: uuid.UUID


class WSServerPong(BaseModel):
    type: Literal["pong"] = "pong"


class WSServerError(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


class WSServerWelcome(BaseModel):
    type: Literal["welcome"] = "welcome"
    message: str = "NEXUS WS - send auth first"
    version: int = 1


# Union types for parsing
WSClientMessage = Union[WSClientAuth, WSClientSubscribe, WSClientUnsubscribe, WSClientPing]

# For server, event envelope will be transmitted as raw EventEnvelope JSON, not wrapped in protocol
# But we have typed errors and control messages
