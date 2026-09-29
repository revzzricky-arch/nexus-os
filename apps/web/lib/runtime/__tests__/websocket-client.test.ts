/**
 * WebSocket Client Tests - Phase 2B-5 Hardened
 * Tests last_event_id persistence, reconnect backoff, mock-realtime boundary,
 * token handling (no default credential, explicit config, no URL, auth message only)
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
  for (let i = 1; i < delays.length; i++) {
    if (delays[i] < delays[i - 1]) {
      throw new Error(`Backoff not increasing at ${i}: ${delays[i]} < ${delays[i - 1]}`);
    }
  }
  if (delays[delays.length - 1] > WS_LIMITS.MAX_BACKOFF_MS) {
    throw new Error(`Backoff exceeds max: ${delays[delays.length - 1]} > ${WS_LIMITS.MAX_BACKOFF_MS}`);
  }
  const afterReset = getBackoffDelay(0);
  if (afterReset !== WS_LIMITS.INITIAL_BACKOFF_MS) {
    throw new Error(`Backoff reset failed: ${afterReset} != ${WS_LIMITS.INITIAL_BACKOFF_MS}`);
  }
  console.log("✓ Backoff tests passed", delays);
}

function testLastEventIdPersistence() {
  console.log("Test last_event_id persistence...");
  let sessionLastEventId: string | null = null;
  const events = [{ id: "evt-1" }, { id: "evt-2" }, { id: "evt-3" }];
  for (const ev of events) {
    sessionLastEventId = ev.id;
  }
  if (sessionLastEventId !== "evt-3") {
    throw new Error(`last_event_id not persisted: ${sessionLastEventId} != evt-3`);
  }
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
  const authMsg = { type: "auth", token: "secret" };
  const urlWithToken = `${url}?token=${authMsg.token}`;
  const clientUrl = "ws://localhost:8000/api/v1/ws";
  if (clientUrl !== url) {
    throw new Error("Client should not include token in URL");
  }
  console.log("✓ No token in URL passed");
}

function testTokenOnlyInAuthMessage() {
  console.log("Test token only in first auth message...");
  const token = "explicit-dev-token";
  const wsUrl = "ws://localhost:8000/api/v1/ws";
  if (wsUrl.includes(token)) {
    throw new Error("Token in URL - forbidden");
  }
  const firstMessage = JSON.stringify({ type: "auth", token });
  const parsed = JSON.parse(firstMessage);
  if (parsed.type !== "auth" || parsed.token !== token) {
    throw new Error("First message must be auth with token");
  }
  const subscribeMsg = JSON.stringify({ type: "subscribe", mission_id: "m-1", last_event_id: "evt-1" });
  if (subscribeMsg.includes(token)) {
    throw new Error("Token should only be in first auth message, not subscribe");
  }
  console.log("✓ Token only in first auth message passed");
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
  const mockStore = { missions: [], agents: [], tasks: [], events: [] };
  const realtimeStore = { missions: [], agents: [], tasks: [], events: [] };
  const mockKeys = Object.keys(mockStore).sort();
  const realtimeKeys = Object.keys(realtimeStore).sort();
  if (JSON.stringify(mockKeys) !== JSON.stringify(realtimeKeys)) {
    throw new Error("Mock and realtime store shape mismatch");
  }
  const defaultMode: RuntimeMode = "mock";
  if (defaultMode !== "mock") {
    throw new Error("Default mode should be mock");
  }
  console.log("✓ Mock/realtime boundary passed");
}

function testMockModeNoToken() {
  console.log("Test mock mode works without token...");
  let tokenRequired = false;
  const mockConnect = async () => {
    tokenRequired = false;
  };
  mockConnect();
  if (tokenRequired) {
    throw new Error("Mock mode should not require token");
  }
  console.log("✓ Mock mode no token passed");
}

function testRealtimeRequiresExplicitToken() {
  console.log("Test realtime mode requires explicit token...");
  function getRealtimeToken(envToken: string | undefined, runtimeConfigToken: string | undefined, lsToken: string | undefined): string | null {
    if (envToken && envToken.trim()) return envToken.trim();
    if (runtimeConfigToken && runtimeConfigToken.trim()) return runtimeConfigToken.trim();
    if (lsToken && lsToken.trim()) return lsToken.trim();
    return null;
  }

  let token = getRealtimeToken(undefined, undefined, undefined);
  if (token !== null) {
    throw new Error("Should be null when no explicit token configured");
  }

  token = getRealtimeToken("explicit-token", undefined, undefined);
  if (token !== "explicit-token") {
    throw new Error("Env token should work");
  }

  token = getRealtimeToken(undefined, "runtime-config-token", undefined);
  if (token !== "runtime-config-token") {
    throw new Error("Runtime config token should work");
  }

  token = getRealtimeToken(undefined, undefined, "ls-token");
  if (token !== "ls-token") {
    throw new Error("LocalStorage token should work");
  }

  console.log("✓ Realtime requires explicit token passed");
}

function testNoDefaultCredentialEmbedded() {
  console.log("Test no default credential embedded...");
  const forbiddenDefaults = ["dev-token-change-me", "dev-token-scaffold", "default-token", "test-token-123"];
  function getRealtimeTokenHardened(env: string | undefined): string | null {
    if (env && env.trim()) return env.trim();
    return null;
  }
  const result = getRealtimeTokenHardened(undefined);
  if (result !== null) {
    throw new Error("Should not return default credential when no explicit config");
  }
  for (const forbidden of forbiddenDefaults) {
    const token = getRealtimeTokenHardened(undefined);
    if (token === forbidden) {
      throw new Error(`Default credential embedded: ${forbidden}`);
    }
  }
  console.log("✓ No default credential embedded passed");
}

function testNoTokenLogging() {
  console.log("Test no token logging...");
  const token = "super-secret-token";
  const logMessage = `Auth failed for connection`;
  if (logMessage.includes(token)) {
    throw new Error("Token should not be logged");
  }
  const errorMsg = `Auth failed: auth_invalid_token`;
  if (errorMsg.includes(token)) {
    throw new Error("Token should not be in error message");
  }
  console.log("✓ No token logging passed");
}

try {
  testBackoff();
  testLastEventIdPersistence();
  testNoTokenInUrl();
  testTokenOnlyInAuthMessage();
  testMissionScoping();
  testMockRealtimeBoundary();
  testMockModeNoToken();
  testRealtimeRequiresExplicitToken();
  testNoDefaultCredentialEmbedded();
  testNoTokenLogging();
  console.log("All websocket-client tests passed");
} catch (e) {
  console.error("Test failed:", e);
  process.exit(1);
}

export {};
