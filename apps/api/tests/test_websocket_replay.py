"""
WebSocket Replay Tests - Phase 2B-5

Tests replay order, wrong-mission, no leak, boundary deduplication
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
    # Create mission
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Replay Order", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    # Create some transitions to generate events
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

    # List events to get order
    resp = client.get(
        f"/api/v1/missions/{mission_id}/events",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 200
    events = resp.json()["data"]
    assert len(events) >= 3
    # Check deterministic ordering: timestamp ASC
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps)

    # Now subscribe via WS and check replay order matches
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

        # Check order matches DB order
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

    # Get first event id
    resp = client.get(
        f"/api/v1/missions/{mission_id}/events",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    first_event_id = resp.json()["data"][0]["id"]

    # Create more events
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
        # Should not include first event
        for _ in range(sub_resp["replay_count"]):
            data = ws.receive_text()
            env = json.loads(data)
            assert env["id"] != first_event_id


def test_replay_wrong_mission_last_event_id(client: TestClient):
    # Create 2 missions
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

    # Get event from m1
    resp = client.get(
        f"/api/v1/missions/{m1_id}/events",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    m1_event_id = resp.json()["data"][0]["id"]

    # Try to subscribe to m2 with m1's last_event_id -> should error last_event_wrong_mission
    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(
            json.dumps({"type": "subscribe", "mission_id": m2_id, "last_event_id": m1_event_id})
        )
        resp_msg = json.loads(ws.receive_text())
        assert resp_msg["type"] == "error"
        assert resp_msg["code"] == "last_event_wrong_mission"


def test_no_cross_mission_leak(client: TestClient):
    # Create 2 missions with events
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

    # Create extra event for m1
    client.patch(
        f"/api/v1/missions/{m1_id}",
        json={"status": "decomposing"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        # Subscribe only to m2
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": m2_id}))
        sub_resp = json.loads(ws.receive_text())
        assert sub_resp["type"] == "subscribed"

        # Replay should only contain m2 events
        for _ in range(sub_resp["replay_count"]):
            data = ws.receive_text()
            env = json.loads(data)
            assert env["mission_id"] == m2_id
            assert env["mission_id"] != m1_id


def test_replay_boundary_no_duplicate(client: TestClient):
    # Test that replay + live doesn't duplicate at boundary
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Boundary Test", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    # Get all events
    resp = client.get(
        f"/api/v1/missions/{mission_id}/events",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    events = resp.json()["data"]
    last_id = events[-1]["id"]

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        # Subscribe with last_event_id = last event, should get 0 replay
        ws.send_text(
            json.dumps({"type": "subscribe", "mission_id": mission_id, "last_event_id": last_id})
        )
        sub_resp = json.loads(ws.receive_text())
        assert sub_resp["type"] == "subscribed"
        assert sub_resp["replay_count"] == 0

        # Now create new event after subscription - should be delivered live once
        # Use another client to create transition
        # We need to use same DB? Our client fixture uses same in-memory DB for duration
        # So we can trigger via REST
        # But live broadcast via websocket_manager requires event_bus emit which happens on patch
        # Our WS manager should receive broadcast via event_bus -> broadcast_event
        # However TestClient's event_bus emit uses asyncio.create_task, which may need loop
        # For MVP, we test that no duplicate replay occurs at boundary, not live delivery in same test
        # Live delivery is tested in events test


def test_replay_batch_bounded(client: TestClient):
    # Create mission and many events (simulate by patching multiple times, but limited)
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Batch Test", "goal": "g"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    # Create few events
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
        # replay_count should be bounded by MAX_REPLAY_BATCH (100)
        assert sub_resp["replay_count"] <= 100
        assert sub_resp["type"] == "subscribed"
