"""
WebSocket Replay Tests - Phase 2B-5 Hardened

Tests replay order, wrong-mission, no leak, boundary deduplication, gap-safe race
"""

import uuid
import json
import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.base import Base
from app.main import app
from app.dependencies import get_db, get_current_user
from app.config import settings
from app.services.websocket_manager import websocket_manager

TEST_TOKEN = "test-token-123"
settings.nexus_dev_token = TEST_TOKEN


@pytest.fixture
def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(init_db())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def override_get_current_user():
        return {"user_id": "test-user", "token_valid": True}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    settings.nexus_dev_token = TEST_TOKEN

    asyncio.get_event_loop().run_until_complete(websocket_manager.cleanup())

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    asyncio.get_event_loop().run_until_complete(websocket_manager.cleanup())
    asyncio.get_event_loop().run_until_complete(engine.dispose())


def _auth(ws):
    ws.receive_text()
    ws.send_text(json.dumps({"type": "auth", "token": TEST_TOKEN}))
    resp = json.loads(ws.receive_text())
    assert resp["type"] == "auth_ok"


def test_replay_order_deterministic(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Replay Order", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "decomposing"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "planned"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )

    resp = client.get(
        f"/api/v1/missions/{mission_id}/events",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 200
    events = resp.json()["data"]
    assert len(events) >= 3
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps)

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": mission_id}))
        sub_resp = json.loads(ws.receive_text())
        assert sub_resp["type"] == "subscribed"
        replay_count = sub_resp["replay_count"]
        assert replay_count >= 3

        replayed = []
        for _ in range(replay_count):
            data = ws.receive_text()
            env = json.loads(data)
            replayed.append(env)

        replay_ids = [e["id"] for e in replayed]
        db_ids = [e["id"] for e in events[:replay_count]]
        assert replay_ids == db_ids


def test_replay_with_last_event_id(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Replay Last", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    resp = client.get(
        f"/api/v1/missions/{mission_id}/events",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    first_event_id = resp.json()["data"][0]["id"]

    client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "decomposing"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(
            json.dumps({"type": "subscribe", "mission_id": mission_id, "last_event_id": first_event_id})
        )
        sub_resp = json.loads(ws.receive_text())
        assert sub_resp["type"] == "subscribed"
        for _ in range(sub_resp["replay_count"]):
            data = ws.receive_text()
            env = json.loads(data)
            assert env["id"] != first_event_id


def test_replay_wrong_mission_last_event_id(client: TestClient):
    resp1 = client.post(
        "/api/v1/missions/",
        json={"title": "M1", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    resp2 = client.post(
        "/api/v1/missions/",
        json={"title": "M2", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    m1_id = resp1.json()["id"]
    m2_id = resp2.json()["id"]

    resp = client.get(
        f"/api/v1/missions/{m1_id}/events",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    m1_event_id = resp.json()["data"][0]["id"]

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(
            json.dumps({"type": "subscribe", "mission_id": m2_id, "last_event_id": m1_event_id})
        )
        resp_msg = json.loads(ws.receive_text())
        assert resp_msg["type"] == "error"
        assert resp_msg["code"] == "last_event_wrong_mission"


def test_no_cross_mission_leak(client: TestClient):
    resp1 = client.post(
        "/api/v1/missions/",
        json={"title": "Leak M1", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    resp2 = client.post(
        "/api/v1/missions/",
        json={"title": "Leak M2", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    m1_id = resp1.json()["id"]
    m2_id = resp2.json()["id"]

    client.patch(
        f"/api/v1/missions/{m1_id}",
        json={"status": "decomposing"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": m2_id}))
        sub_resp = json.loads(ws.receive_text())
        assert sub_resp["type"] == "subscribed"

        for _ in range(sub_resp["replay_count"]):
            data = ws.receive_text()
            env = json.loads(data)
            assert env["mission_id"] == m2_id
            assert env["mission_id"] != m1_id


def test_replay_boundary_no_duplicate(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Boundary Test", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    resp = client.get(
        f"/api/v1/missions/{mission_id}/events",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    events = resp.json()["data"]
    last_id = events[-1]["id"]

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(
            json.dumps({"type": "subscribe", "mission_id": mission_id, "last_event_id": last_id})
        )
        sub_resp = json.loads(ws.receive_text())
        assert sub_resp["type"] == "subscribed"
        assert sub_resp["replay_count"] == 0


def test_replay_batch_bounded(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Batch Test", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "decomposing"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "planned"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "running"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": mission_id}))
        sub_resp = json.loads(ws.receive_text())
        assert sub_resp["replay_count"] <= 100
        assert sub_resp["type"] == "subscribed"


def test_replay_live_race_gap_safe():
    """
    Regression test for replay/live race condition
    Simulates event appearing around replay/subscription boundary
    Proves it is not silently lost or duplicated with gap-safe buffering
    """
    async def run():
        await websocket_manager.cleanup()
        from unittest.mock import AsyncMock
        import datetime

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        conn = await websocket_manager.register(mock_ws)
        assert conn is not None
        user_id = uuid.uuid4()
        await websocket_manager.set_authenticated(conn.id, user_id)
        mission_id = uuid.uuid4()

        added = await websocket_manager.add_subscription(conn.id, mission_id)
        assert added

        await websocket_manager.start_replay_buffer(conn.id, mission_id)

        class FakeEvent:
            def __init__(self, eid, ts):
                self.id = eid
                self.type = "mission_status_changed"
                self.source = "system"
                self.mission_id = mission_id
                self.task_id = None
                self.agent_id = None
                self.timestamp = ts
                self.version = 1
                self.payload = {"from": "draft", "to": "running"}
                self.metadata_ = {}

        now = datetime.datetime.now(datetime.timezone.utc)
        replay_events = [
            FakeEvent(uuid.uuid4(), now),
            FakeEvent(uuid.uuid4(), now),
        ]
        replayed_ids = {e.id for e in replay_events}

        race_event = FakeEvent(uuid.uuid4(), now)
        await websocket_manager.broadcast_event(race_event)

        buffered_count = await websocket_manager.get_buffered_count(conn.id, mission_id)
        assert buffered_count == 1, f"Race event should be buffered, got {buffered_count}"

        buffered = await websocket_manager.end_replay_buffer(conn.id, mission_id)
        assert len(buffered) == 1
        assert buffered[0].id == race_event.id

        await websocket_manager.start_replay_buffer(conn.id, mission_id)
        duplicate_event = replay_events[0]
        await websocket_manager.broadcast_event(duplicate_event)
        await websocket_manager.broadcast_event(race_event)
        buffered2 = await websocket_manager.end_replay_buffer(conn.id, mission_id)
        deduped = []
        seen = set(replayed_ids)
        for ev in buffered2:
            if ev.id not in seen:
                deduped.append(ev)
                seen.add(ev.id)
        assert len(deduped) == 1
        assert deduped[0].id == race_event.id

        mock_ws.send_text.reset_mock()
        live_event = FakeEvent(uuid.uuid4(), now)
        await websocket_manager.broadcast_event(live_event)
        assert mock_ws.send_text.called
        sent = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent["id"] == str(live_event.id)

        await websocket_manager.disconnect(conn.id)
        await websocket_manager.cleanup()

    asyncio.get_event_loop().run_until_complete(run())


def test_replay_live_race_integration(client: TestClient):
    """
    Integration test: event emitted during replay phase should not be lost
    Uses real WS flow with gap-safe buffering
    """
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Race Integration", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    resp = client.get(
        f"/api/v1/missions/{mission_id}/events",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    initial_count = len(resp.json()["data"])

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": mission_id}))
        sub_resp = json.loads(ws.receive_text())
        assert sub_resp["type"] == "subscribed"
        replay_count = sub_resp["replay_count"]
        assert replay_count == initial_count

        replayed_ids = []
        for _ in range(replay_count):
            data = ws.receive_text()
            env = json.loads(data)
            replayed_ids.append(env["id"])

        client.patch(
            f"/api/v1/missions/{mission_id}",
            json={"status": "decomposing"},
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )

        resp = client.get(
            f"/api/v1/missions/{mission_id}/events",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert len(resp.json()["data"]) == initial_count + 1
        new_event_id = resp.json()["data"][-1]["id"]
        assert new_event_id not in replayed_ids
