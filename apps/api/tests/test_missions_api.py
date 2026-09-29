"""
Missions API Tests - Phase 2B-2
Auth, create, list, get, missing, validation, transitions, invalid, cancel, pagination
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.db.base import Base
from app.models.mission import Mission
from app.models.task import Task
from app.main import app
from app.dependencies import get_db, get_current_user
from app.config import settings

# Test token
TEST_TOKEN = "test-token-123"
settings.nexus_dev_token = TEST_TOKEN


@pytest.fixture
def client():
    import asyncio

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(init_db())

    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def override_get_current_user():
        return {"user_id": "dev-user", "token_valid": True}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    asyncio.get_event_loop().run_until_complete(engine.dispose())


def test_health_no_auth():
    # Health should work without auth (optional)
    with TestClient(app) as c:
        resp = c.get("/health")
        assert resp.status_code == 200


def test_auth_required():
    # Override only get_db, not get_current_user, to test auth failure
    import asyncio

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(setup())

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

    app.dependency_overrides[get_db] = override_get_db
    # Do NOT override get_current_user - use real auth

    try:
        with TestClient(app) as c:
            # No token
            resp = c.get("/api/v1/missions/")
            assert resp.status_code == 401
            assert resp.json()["error"]["code"] == "unauthorized"

            # Invalid token
            resp = c.get("/api/v1/missions/", headers={"Authorization": "Bearer wrong-token"})
            assert resp.status_code == 401

            # Valid token via Authorization header
            resp = c.get("/api/v1/missions/", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
            assert resp.status_code == 200

            # Valid token via X-Nexus-Token header
            resp = c.get("/api/v1/missions/", headers={"X-Nexus-Token": TEST_TOKEN})
            assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()
        asyncio.get_event_loop().run_until_complete(engine.dispose())


def test_create_mission(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Test Mission", "goal": "Test goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["title"] == "Test Mission"
    assert data["status"] == "draft"
    assert "id" in data


def test_create_mission_validation(client: TestClient):
    # Empty title
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code in (400, 422)

    # Empty goal
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "title", "goal": ""},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code in (400, 422)

    # Missing fields
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "only title"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code in (400, 422)


def test_list_missions_pagination(client: TestClient):
    # Create 5 missions
    for i in range(5):
        resp = client.post(
            "/api/v1/missions/",
            json={"title": f"M{i}", "goal": "goal"},
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp.status_code == 201

    resp = client.get("/api/v1/missions/?limit=2&offset=0", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 5
    assert len(data["data"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    resp2 = client.get("/api/v1/missions/?limit=2&offset=2", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["data"]) == 2

    # Deterministic ordering - no overlap
    ids1 = {m["id"] for m in data["data"]}
    ids2 = {m["id"] for m in data2["data"]}
    assert ids1.isdisjoint(ids2)


def test_list_missions_status_filter(client: TestClient):
    # Create mission
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Filter Test", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    # List with status filter draft
    resp = client.get("/api/v1/missions/?status=draft", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(m["status"] == "draft" for m in data["data"])

    # Invalid status filter should return validation error
    resp = client.get("/api/v1/missions/?status=invalid_status", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_get_mission(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Get Test", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    resp = client.get(f"/api/v1/missions/{mission_id}", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "mission" in data
    assert "task_summary" in data
    assert data["mission"]["id"] == mission_id
    assert data["task_summary"]["total"] == 0


def test_get_mission_not_found(client: TestClient):
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/missions/{fake_id}", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "mission_not_found"


def test_update_mission_valid_transition(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Transition Test", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    # draft -> decomposing valid
    resp = client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "decomposing"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "decomposing"

    # decomposing -> planned valid
    resp = client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "planned"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "planned"


def test_update_mission_invalid_transition(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Invalid Transition Test", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    # draft -> running invalid
    resp = client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "running"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_transition"


def test_cancel_mission(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Cancel Test", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    # Cancel
    resp = client.post(f"/api/v1/missions/{mission_id}/cancel", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    # Cancel again idempotent
    resp = client.post(f"/api/v1/missions/{mission_id}/cancel", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_invalid_from_completed(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Cancel Invalid", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    # Move to completed via valid transitions
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "decomposing"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "planned"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "running"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "completed"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})

    # Cancel from completed should fail
    resp = client.post(f"/api/v1/missions/{mission_id}/cancel", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_transition"


def test_get_mission_tasks(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Tasks Test", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    resp = client.get(f"/api/v1/missions/{mission_id}/tasks", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["data"]) == 0


def test_get_mission_tasks_no_cross_leak(client: TestClient):
    # Create 2 missions
    resp1 = client.post("/api/v1/missions/", json={"title": "M1", "goal": "g"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    resp2 = client.post("/api/v1/missions/", json={"title": "M2", "goal": "g"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    m1_id = resp1.json()["id"]
    m2_id = resp2.json()["id"]

    # List tasks for m1 should not include m2 tasks (both empty initially)
    resp = client.get(f"/api/v1/missions/{m1_id}/tasks", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200

    # Non-existent mission should 404
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/missions/{fake_id}/tasks", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 404


def test_get_mission_events(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Events Test", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    resp = client.get(f"/api/v1/missions/{mission_id}/events", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["data"]) >= 1
    assert data["data"][0]["type"] == "mission_created"
    assert data["data"][0]["mission_id"] == mission_id


def test_get_mission_events_filters(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Events Filter", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    # Transition to create more events
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "decomposing"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})

    # Filter by type
    resp = client.get(f"/api/v1/missions/{mission_id}/events?type=mission_created", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert all(e["type"] == "mission_created" for e in resp.json()["data"])

    resp = client.get(f"/api/v1/missions/{mission_id}/events?type=mission_status_changed", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert all(e["type"] == "mission_status_changed" for e in resp.json()["data"])


def test_get_mission_events_last_event_id(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Events Replay", "goal": "goal"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    # Get first event id
    resp = client.get(f"/api/v1/missions/{mission_id}/events", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    first_event_id = resp.json()["data"][0]["id"]

    # Transition to create second event
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "decomposing"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})

    # Replay after first event
    resp = client.get(f"/api/v1/missions/{mission_id}/events?last_event_id={first_event_id}", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    # Should not include first event
    assert all(e["id"] != first_event_id for e in data["data"])


def test_cancel_mission_does_not_swallow_job_cancellation_failure():
    """Regression: job cancellation failure must NOT be silently swallowed leaving mission cancelled but job running"""
    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.base import Base
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    import asyncio

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(init_db())

    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def override_get_current_user():
        return {"user_id": "dev-user", "token_valid": True}

    from app.dependencies import get_db, get_current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Do not raise server exceptions, we want to check response status
    test_client = TestClient(app, raise_server_exceptions=False)

    try:
        resp = test_client.post(
            "/api/v1/missions/",
            json={"title": "Cancel Job Fail Test", "goal": "goal"},
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp.status_code == 201
        mission_id = resp.json()["id"]

        # Mock job_service.cancel_jobs_for_mission to fail
        with patch("app.services.job.job_service.cancel_jobs_for_mission", new_callable=AsyncMock) as mock_cancel:
            mock_cancel.side_effect = Exception("Simulated job cancellation DB failure")

            resp = test_client.post(f"/api/v1/missions/{mission_id}/cancel", headers={"Authorization": f"Bearer {TEST_TOKEN}"})

            # Should NOT silently succeed - must surface error (400 or 500, not 200)
            assert resp.status_code != 200, f"Mission cancellation should not silently succeed when job cancellation fails, got {resp.status_code} body {resp.text}"

            # Verify mission is NOT left in inconsistent state (rolled back to draft, not cancelled)
            resp_get = test_client.get(f"/api/v1/missions/{mission_id}", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
            if resp_get.status_code == 200:
                status = resp_get.json()["mission"]["status"]
                assert status != "cancelled", f"Mission should not be cancelled when job cancellation fails, got {status} - indicates swallowed error"
    finally:
        app.dependency_overrides.clear()
        asyncio.get_event_loop().run_until_complete(engine.dispose())
