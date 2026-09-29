"""
Event Bus Service - Scaffold Placeholder
No Redis/WS streaming yet, only contract defined
See packages/shared/src/events.ts for EventEnvelope
"""


class EventBusService:
    """Scaffold placeholder for event bus - Redis Streams + PubSub planned"""

    async def emit(self, event_type: str, mission_id: str, payload: dict):
        # Scaffold: log only, no real Redis
        return {
            "id": "scaffold-event-id",
            "type": event_type,
            "mission_id": mission_id,
            "payload": payload,
            "status": "scaffold - no real Redis yet",
        }

    async def subscribe(self, channel: str):
        return {"channel": channel, "status": "scaffold - no real subscription yet"}


event_bus_service = EventBusService()
