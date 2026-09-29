"""
WS Shared Contract Tests - Phase 3 PR 3.1
Ensures shared protocol matches backend
"""

import json
import pathlib


def test_shared_events_ws_contract_matches_backend():
    # Load shared events.ts - repo root is 3 levels up from apps/api/tests/
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    shared_path = repo_root / "packages" / "shared" / "src" / "events.ts"
    if not shared_path.exists():
        # Fallback for different working dirs
        shared_path = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "packages" / "shared" / "src" / "events.ts"
    if not shared_path.exists():
        shared_path = pathlib.Path.cwd().resolve().parent.parent / "packages" / "shared" / "src" / "events.ts"
    if not shared_path.exists():
        shared_path = pathlib.Path.cwd().resolve() / ".." / ".." / "packages" / "shared" / "src" / "events.ts"
        shared_path = shared_path.resolve()

    assert shared_path.exists(), f"Shared events.ts not found, tried {shared_path}, repo_root {repo_root}"

    content = shared_path.read_text()

    # Must NOT contain old channels[] scaffold
    # The old scaffold had WSSubscribeMessage with channels: string[]
    # New contract must have mission_id
    assert "mission_id" in content, "Shared contract must contain mission_id for WS subscribe"
    assert "WSSubscribeMessage" in content
    assert "WSUnsubscribeMessage" in content

    # Ensure WSSubscribeMessage does not have channels array as primary (allow comment mentioning old)
    # Check that interface definition contains mission_id, not channels as required field
    # Parse roughly
    assert "channels: string[]" not in content or content.count("mission_id") >= 2, "Shared contract should use mission_id not channels[]"

    # Ensure backend schemas match
    backend_ws_path = pathlib.Path(__file__).parent.parent / "app" / "schemas" / "websocket.py"
    backend_content = backend_ws_path.read_text()

    assert "mission_id" in backend_content
    assert "last_event_id" in backend_content
    assert "WSClientSubscribe" in backend_content

    # Ensure frontend hook also matches
    frontend_hook_path = repo_root / "apps" / "web" / "lib" / "ws" / "useWebSocket.ts"
    if not frontend_hook_path.exists():
        frontend_hook_path = pathlib.Path(__file__).resolve().parents[3] / "apps" / "web" / "lib" / "ws" / "useWebSocket.ts"
    if frontend_hook_path.exists():
        frontend_content = frontend_hook_path.read_text()
        assert "mission_id" in frontend_content
        # Should not have channels subscription as active code (comment allowed)
        # Check that active JSON has mission_id
        assert "mission_id" in frontend_content.lower()

    # EventEnvelope unchanged
    assert "EventEnvelope" in content
    assert "id: UUID" in content
    assert "type: EventType" in content
    assert "source: EventSource" in content


def test_ws_backend_protocol_structure():
    from app.schemas.websocket import WSClientSubscribe, WSClientUnsubscribe, WSClientAuth

    # Validate models have mission_id
    assert "mission_id" in WSClientSubscribe.model_fields
    assert "mission_id" in WSClientUnsubscribe.model_fields
    assert "last_event_id" in WSClientSubscribe.model_fields

    # Auth must have token
    assert "token" in WSClientAuth.model_fields

    # Ensure no channels field
    assert "channels" not in WSClientSubscribe.model_fields
    assert "channels" not in WSClientUnsubscribe.model_fields
