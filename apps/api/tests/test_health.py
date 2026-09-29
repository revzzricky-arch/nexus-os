"""
Backend smoke tests - /health and /version
Scaffold phase
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "nexus-api"
    assert "codename" in data
    assert data["codename"] == "NEXUS"


def test_version():
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "nexus-api"
    assert "version" in data
    assert "codename" in data
    assert data["codename"] == "NEXUS"
    assert "stack" in data
    assert data["stack"]["deployment"] == "Docker Compose (MVP, D7)"


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "nexus-api"
    assert data["scaffold"] is True
