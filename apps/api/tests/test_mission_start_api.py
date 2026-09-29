"""
Mission Start API Tests - Phase 2B-3
Valid start, invalid start, mission not found, successful execution, failure handling
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.base import Base
from app.main import app
from app.dependencies import get_db, get_current_user
from app.config import settings

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

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    asyncio.get_event_loop().run_until_complete(engine.dispose())


def test_start_mission_not_found(client: TestClient):
    fake_id = str(uuid.uuid4())
    resp = client.post(f"/api/v1/missions/{fake_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "mission_not_found"


def test_start_mission_valid(client: TestClient):
    # Create mission
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Start Test", "goal": "Research AI trends", "template": "research"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    # Start mission
    resp = client.post(f"/api/v1/missions/{mission_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mission_id"] == mission_id
    assert data["status"] in ["completed", "failed"]
    assert "total_tasks" in data
    assert data["total_tasks"] >= 2


def test_start_mission_successful_execution(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Success Test", "goal": "Build a simple web app", "template": "code"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    resp = client.post(f"/api/v1/missions/{mission_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "completed"
    assert data["completed_tasks"] == data["total_tasks"]
    assert data["total_tasks"] >= 3

    # Check mission status via GET
    resp = client.get(f"/api/v1/missions/{mission_id}", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["mission"]["status"] == "completed"

    # Check tasks created
    resp = client.get(f"/api/v1/missions/{mission_id}/tasks", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    tasks_data = resp.json()
    assert tasks_data["total"] >= 3
    assert all(t["status"] == "completed" for t in tasks_data["data"])

    # Check events emitted
    resp = client.get(f"/api/v1/missions/{mission_id}/events", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    events_data = resp.json()
    event_types = [e["type"] for e in events_data["data"]]
    assert "mission_created" in event_types
    assert "mission_status_changed" in event_types
    assert "task_status_changed" in event_types
    assert "agent_state_changed" in event_types


def test_start_mission_invalid_state(client: TestClient):
    # Create and start mission
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Invalid Start", "goal": "Test", "template": "general"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    # Start first time - should succeed
    resp = client.post(f"/api/v1/missions/{mission_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # Try to start again from completed - should fail (invalid transition)
    resp = client.post(f"/api/v1/missions/{mission_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_start_mission_different_templates(client: TestClient):
    for template in ["research", "code", "analysis", "general"]:
        resp = client.post(
            "/api/v1/missions/",
            json={"title": f"{template} mission", "goal": f"Test {template}", "template": template},
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp.status_code == 201
        mission_id = resp.json()["id"]

        resp = client.post(f"/api/v1/missions/{mission_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert resp.status_code == 200, f"Failed for template {template}: {resp.text}"
        assert resp.json()["status"] == "completed"


def test_start_mission_lifecycle_transitions(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Lifecycle Test", "goal": "Test lifecycle", "template": "general"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    # Check initial status draft
    resp = client.get(f"/api/v1/missions/{mission_id}", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.json()["mission"]["status"] == "draft"

    # Start
    resp = client.post(f"/api/v1/missions/{mission_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200

    # Check final status completed and events show transitions
    resp = client.get(f"/api/v1/missions/{mission_id}/events?type=mission_status_changed", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    status_changes = resp.json()["data"]

    # Should have at least draft->decomposing, decomposing->planned, planned->running, running->completed
    transitions = [(e["payload"]["from"], e["payload"]["to"]) for e in status_changes]

    assert ("draft", "decomposing") in transitions
    assert ("decomposing", "planned") in transitions
    assert ("planned", "running") in transitions
    assert ("running", "completed") in transitions
