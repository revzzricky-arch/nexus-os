"""
WebSocket Protocol Tests - Phase 2B-5

Tests invalid JSON, invalid type, subscribe/unsubscribe, oversized
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
    ws.receive_text()  # welcome
    ws.send_text(json.dumps({"type": "auth", "token": TEST_TOKEN}))
    resp = json.loads(ws.receive_text())
    assert resp["type"] == "auth_ok"


def test_invalid_json(client: TestClient):
    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text("not json {")
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert resp["code"] == "invalid_json"


def test_invalid_message_type(client: TestClient):
    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(json.dumps({"type": "unknown_type_xyz"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert resp["code"] == "invalid_message_type"


def test_ping_pong(client: TestClient):
    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(json.dumps({"type": "ping"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "pong"


def test_subscribe_invalid_mission_id(client: TestClient):
    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": "not-a-uuid"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert resp["code"] == "invalid_mission_id"


def test_subscribe_mission_not_found(client: TestClient):
    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        fake_id = str(uuid.uuid4())
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": fake_id}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert resp["code"] == "mission_not_found"


def test_subscribe_and_unsubscribe(client: TestClient):
    # Create mission first
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "WS Test", "goal": "test"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": mission_id}))
        resp_msg = json.loads(ws.receive_text())
        assert resp_msg["type"] == "subscribed"
        assert resp_msg["mission_id"] == mission_id
        # Replay may include mission_created event
        # Consume replay events if any (up to replay_count)
        replay_count = resp_msg.get("replay_count", 0)
        for _ in range(replay_count):
            # Each replay is EventEnvelope
            data = ws.receive_text()
            env = json.loads(data)
            assert "id" in env
            assert env["mission_id"] == mission_id

        # Unsubscribe
        ws.send_text(json.dumps({"type": "unsubscribe", "mission_id": mission_id}))
        resp2 = json.loads(ws.receive_text())
        assert resp2["type"] == "unsubscribed"
        assert resp2["mission_id"] == mission_id


def test_subscribe_invalid_last_event_id(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "WS Last Event Test", "goal": "test"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        ws.send_text(
            json.dumps({"type": "subscribe", "mission_id": mission_id, "last_event_id": "not-a-uuid"})
        )
        resp_msg = json.loads(ws.receive_text())
        assert resp_msg["type"] == "error"
        assert resp_msg["code"] == "invalid_last_event_id"


def test_oversized_message(client: TestClient):
    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        # Create oversized payload >32KB
        big = "x" * (35 * 1024)
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": str(uuid.uuid4()), "extra": big}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert resp["code"] == "message_too_large"


def test_too_many_subscriptions(client: TestClient):
    # Create 11 missions
    mission_ids = []
    for i in range(11):
        resp = client.post(
            "/api/v1/missions/",
            json={"title": f"M{i}", "goal": "g"},
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp.status_code == 201
        mission_ids.append(resp.json()["id"])

    with client.websocket_connect("/api/v1/ws") as ws:
        _auth(ws)
        # Subscribe to 10 (max)
        for mid in mission_ids[:10]:
            ws.send_text(json.dumps({"type": "subscribe", "mission_id": mid}))
            resp = json.loads(ws.receive_text())
            assert resp["type"] == "subscribed"
            # consume replay
            for _ in range(resp.get("replay_count", 0)):
                ws.receive_text()

        # 11th should fail
        ws.send_text(json.dumps({"type": "subscribe", "mission_id": mission_ids[10]}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert resp["code"] == "too_many_subscriptions"
