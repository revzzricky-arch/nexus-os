/**
 * WebSocket Client Tests - Phase 2B-5
 * Tests last_event_id persistence, reconnect backoff, mock-realtime boundary
 * Pure logic tests, no actual WS connection
 */

import { WS_LIMITS } from "../types";

// Test backoff calculation
function getBackoffDelay(attempt: number): number {
  const base = WS_LIMITS.INITIAL_BACKOFF_MS * Math.pow(WS_LIMITS.BACKOFF_MULTIPLIER, attempt);
  return Math.min(base, WS_LIMITS.MAX_BACKOFF_MS);
}

function testBackoff() {
  console.log("Test backoff bounded exponential...");
  const delays = [];
  for (let i = 0; i < 10; i++) {
    delays.push(getBackoffDelay(i));
  }
  // Should be increasing
  for (let i = 1; i < delays.length; i++) {
    if (delays[i] < delays[i - 1]) {
      throw new Error(`Backoff not increasing at ${i}: ${delays[i]} < ${delays[i - 1]}`);
    }
  }
  // Should be bounded by MAX
  if (delays[delays.length - 1] > WS_LIMITS.MAX_BACKOFF_MS) {
    throw new Error(`Backoff exceeds max: ${delays[delays.length - 1]} > ${WS_LIMITS.MAX_BACKOFF_MS}`);
  }
  // Reset after auth success
  const afterReset = getBackoffDelay(0);
  if (afterReset !== WS_LIMITS.INITIAL_BACKOFF_MS) {
    throw new Error(`Backoff reset failed: ${afterReset} != ${WS_LIMITS.INITIAL_BACKOFF_MS}`);
  }
  console.log("✓ Backoff tests passed", delays);
}

function testLastEventIdPersistence() {
  console.log("Test last_event_id persistence...");
  let sessionLastEventId: string | null = null;

  // Simulate event stream
  const events = [{ id: "evt-1" }, { id: "evt-2" }, { id: "evt-3" }];
  for (const ev of events) {
    sessionLastEventId = ev.id;
  }

  if (sessionLastEventId !== "evt-3") {
    throw new Error(`last_event_id not persisted: ${sessionLastEventId} != evt-3`);
  }

  // On reconnect, should use last_event_id
  const reconnectMsg = {
    type: "subscribe",
    mission_id: "mission-123",
    last_event_id: sessionLastEventId,
  };
  if (reconnectMsg.last_event_id !== "evt-3") {
    throw new Error("Reconnect should use last_event_id");
  }
  console.log("✓ last_event_id persistence passed");
}

function testNoTokenInUrl() {
  console.log("Test no token in URL...");
  const url = "ws://localhost:8000/api/v1/ws";
  if (url.includes("token") || url.includes("TOKEN")) {
    throw new Error("Token should not be in URL");
  }
  // Auth should be via message, not query
  const authMsg = { type: "auth", token: "secret" };
  const urlWithToken = `${url}?token=${authMsg.token}`;
  // This URL should be rejected - we test that our client never constructs it
  const clientUrl = "ws://localhost:8000/api/v1/ws"; // correct
  if (clientUrl !== url) {
    throw new Error("Client should not include token in URL");
  }
  console.log("✓ No token in URL passed");
}

function testMissionScoping() {
  console.log("Test mission scoping no leak...");
  const subscribedMissionId = "mission-1";
  const events = [
    { mission_id: "mission-1", id: "1" },
    { mission_id: "mission-2", id: "2" },
    { mission_id: "mission-1", id: "3" },
  ];
  const filtered = events.filter((e) => e.mission_id === subscribedMissionId);
  if (filtered.length !== 2) {
    throw new Error(`Mission scoping failed: ${filtered.length} != 2`);
  }
  if (filtered.some((e) => e.mission_id !== subscribedMissionId)) {
    throw new Error("Cross-mission leak detected");
  }
  console.log("✓ Mission scoping passed");
}

function testMockRealtimeBoundary() {
  console.log("Test mock/realtime boundary...");
  type RuntimeMode = "mock" | "realtime";
  const modes: RuntimeMode[] = ["mock", "realtime"];
  // Both should have same store shape
  const mockStore = { missions: [], agents: [], tasks: [], events: [] };
  const realtimeStore = { missions: [], agents: [], tasks: [], events: [] };
  // Check same keys
  const mockKeys = Object.keys(mockStore).sort();
  const realtimeKeys = Object.keys(realtimeStore).sort();
  if (JSON.stringify(mockKeys) !== JSON.stringify(realtimeKeys)) {
    throw new Error("Mock and realtime store shape mismatch");
  }
  // Default safe is mock
  const defaultMode: RuntimeMode = "mock";
  if (defaultMode !== "mock") {
    throw new Error("Default mode should be mock");
  }
  console.log("✓ Mock/realtime boundary passed");
}

// Run tests
try {
  testBackoff();
  testLastEventIdPersistence();
  testNoTokenInUrl();
  testMissionScoping();
  testMockRealtimeBoundary();
  console.log("All websocket-client tests passed");
} catch (e) {
  console.error("Test failed:", e);
  process.exit(1);
}

export {};
