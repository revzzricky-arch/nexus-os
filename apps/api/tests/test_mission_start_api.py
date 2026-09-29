"""
Mission Start API Tests - Phase 3 PR 3.1 Durable Worker
- 202 job/execution IDs idempotency duplicate invalid state missing mission cancellation
Replaces Phase 2B-3 synchronous tests
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
        return {"user_id": "dev-user", "token_valid": True}

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


def test_start_mission_202_with_ids(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Start 202 Test", "goal": "Research AI trends", "template": "research"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 201
    mission_id = resp.json()["id"]

    resp = client.post(f"/api/v1/missions/{mission_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["mission_id"] == mission_id
    assert "execution_id" in data
    assert "job_id" in data
    assert data["status"] == "pending"

    uuid.UUID(data["execution_id"])
    uuid.UUID(data["job_id"])


def test_start_mission_idempotency_duplicate(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Idempotent Test", "goal": "Test", "template": "general"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    idem_key = "test-idem-key-12345"

    resp1 = client.post(
        f"/api/v1/missions/{mission_id}/start",
        headers={"Authorization": f"Bearer {TEST_TOKEN}", "Idempotency-Key": idem_key},
    )
    assert resp1.status_code == 202
    job_id_1 = resp1.json()["job_id"]
    execution_id_1 = resp1.json()["execution_id"]

    resp2 = client.post(
        f"/api/v1/missions/{mission_id}/start",
        headers={"Authorization": f"Bearer {TEST_TOKEN}", "Idempotency-Key": idem_key},
    )
    assert resp2.status_code == 202
    assert resp2.json()["job_id"] == job_id_1
    assert resp2.json()["execution_id"] == execution_id_1

    resp3 = client.post(
        f"/api/v1/missions/{mission_id}/start",
        headers={"Authorization": f"Bearer {TEST_TOKEN}", "Idempotency-Key": "different-key"},
    )
    assert resp3.status_code == 409
    assert resp3.json()["error"]["code"] == "conflict"


def test_start_mission_invalid_state(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Invalid State", "goal": "Test", "template": "general"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    # Transition to completed
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "decomposing"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "planned"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "running"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    client.patch(f"/api/v1/missions/{mission_id}", json={"status": "completed"}, headers={"Authorization": f"Bearer {TEST_TOKEN}"})

    resp = client.post(f"/api/v1/missions/{mission_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_start_mission_cancellation(client: TestClient):
    resp = client.post(
        "/api/v1/missions/",
        json={"title": "Cancel Job Test", "goal": "Test", "template": "general"},
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    mission_id = resp.json()["id"]

    resp = client.post(f"/api/v1/missions/{mission_id}/start", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    resp = client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    resp = client.post(f"/api/v1/missions/{mission_id}/cancel", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200

    resp = client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    # Idempotent cancel
    resp = client.post(f"/api/v1/missions/{mission_id}/cancel", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
