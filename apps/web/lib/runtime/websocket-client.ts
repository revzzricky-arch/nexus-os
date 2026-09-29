"use client";

/**
 * WebSocket Client - Phase 2B-5 Real-Time Runtime Integration
 *
 * Responsibilities:
 * - connect / authenticate / subscribe
 * - reconnect bounded exponential backoff
 * - maintain last_event_id while mission session active
 * - dispatch into Zustand via adapter
 * - disconnect cleanly
 *
 * No WS code in UI components - isolated here
 *
 * Security: no token in URL, no token logging, token from env/header
 */

import { WS_LIMITS, type EventEnvelope, type WSConnectionState } from "./types";

type EventHandler = (envelope: EventEnvelope) => void;
type StateHandler = (state: WSConnectionState) => void;
type ErrorHandler = (code: string, message: string) => void;

interface WSClientOptions {
  url: string;
  token: string;
  missionId: string;
  lastEventId?: string | null;
  onEvent: EventHandler;
  onStateChange?: StateHandler;
  onError?: ErrorHandler;
  onSubscribed?: (missionId: string, replayCount: number) => void;
}

export class RealtimeWebSocketClient {
  private url: string;
  private token: string;
  private missionId: string;
  private lastEventId: string | null;
  private onEvent: EventHandler;
  private onStateChange?: StateHandler;
  private onError?: ErrorHandler;
  private onSubscribed?: (missionId: string, replayCount: number) => void;

  private ws: WebSocket | null = null;
  private state: WSConnectionState = "CLOSED";
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private shouldReconnect = true;
  private isManuallyClosed = false;

  // Persist last_event_id while mission session active
  // In-memory for MVP, could be sessionStorage for page reload
  private sessionLastEventId: string | null = null;

  constructor(options: WSClientOptions) {
    this.url = options.url;
    this.token = options.token;
    this.missionId = options.missionId;
    this.lastEventId = options.lastEventId || null;
    this.sessionLastEventId = options.lastEventId || null;
    this.onEvent = options.onEvent;
    this.onStateChange = options.onStateChange;
    this.onError = options.onError;
    this.onSubscribed = options.onSubscribed;
  }

  private setState(newState: WSConnectionState) {
    this.state = newState;
    this.onStateChange?.(newState);
  }

  private getBackoffDelay(): number {
    const base = WS_LIMITS.INITIAL_BACKOFF_MS * Math.pow(WS_LIMITS.BACKOFF_MULTIPLIER, this.reconnectAttempts);
    return Math.min(base, WS_LIMITS.MAX_BACKOFF_MS);
  }

  private clearTimers() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private startHeartbeat() {
    this.clearHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: "ping" }));
        } catch {
          // ignore
        }
      }
    }, WS_LIMITS.HEARTBEAT_INTERVAL_MS);
  }

  private clearHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  async connect(): Promise<void> {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.shouldReconnect = true;
    this.isManuallyClosed = false;
    this.setState("CONNECTING");

    return new Promise((resolve, reject) => {
      try {
        // No token in URL - per security
        const ws = new WebSocket(this.url);
        this.ws = ws;

        let authTimeout: ReturnType<typeof setTimeout> | null = null;

        ws.onopen = () => {
          this.setState("AUTHENTICATING");
          // Send auth as first message
          try {
            ws.send(JSON.stringify({ type: "auth", token: this.token }));
          } catch {
            reject(new Error("Failed to send auth"));
            return;
          }

          // Auth timeout
          authTimeout = setTimeout(() => {
            if (this.state === "AUTHENTICATING") {
              this.onError?.("auth_timeout", "Authentication timeout");
              ws.close(1008);
              reject(new Error("Auth timeout"));
            }
          }, WS_LIMITS.AUTH_TIMEOUT);
        };

        ws.onmessage = (event) => {
          // Check message size
          if (event.data && typeof event.data === "string" && event.data.length > WS_LIMITS.MAX_MESSAGE_SIZE) {
            this.onError?.("message_too_large", "Message too large");
            return;
          }

          let data: any;
          try {
            data = JSON.parse(event.data);
          } catch {
            this.onError?.("invalid_json", "Invalid JSON");
            return;
          }

          // Handle protocol messages
          if (data.type === "welcome") {
            // ignore, waiting for auth_ok
            return;
          }

          if (data.type === "auth_ok") {
            if (authTimeout) clearTimeout(authTimeout);
            this.setState("AUTHENTICATED");
            this.reconnectAttempts = 0; // reset after auth success
            this.startHeartbeat();

            // Subscribe to mission with last_event_id for replay
            const subscribeMsg: any = {
              type: "subscribe",
              mission_id: this.missionId,
            };
            // Persist last_event_id while session active
            const effectiveLastId = this.sessionLastEventId || this.lastEventId;
            if (effectiveLastId) {
              subscribeMsg.last_event_id = effectiveLastId;
            }

            try {
              ws.send(JSON.stringify(subscribeMsg));
            } catch {
              this.onError?.("subscribe_failed", "Failed to subscribe");
            }
            resolve();
            return;
          }

          if (data.type === "auth_error") {
            if (authTimeout) clearTimeout(authTimeout);
            this.onError?.(data.code || "auth_error", data.message || "Auth failed");
            this.shouldReconnect = false; // don't reconnect on auth error
            ws.close(1008);
            reject(new Error(data.message || "Auth failed"));
            return;
          }

          if (data.type === "subscribed") {
            this.setState("SUBSCRIBED");
            this.onSubscribed?.(data.mission_id, data.replay_count || 0);
            // If replay includes last_event_id, update session tracking
            if (data.last_event_id) {
              this.sessionLastEventId = data.last_event_id;
            }
            return;
          }

          if (data.type === "unsubscribed") {
            this.setState("AUTHENTICATED");
            return;
          }

          if (data.type === "pong") {
            return;
          }

          if (data.type === "error") {
            this.onError?.(data.code || "unknown_error", data.message || "Unknown error");
            return;
          }

          // Otherwise, assume EventEnvelope
          if (data.id && data.type && data.mission_id) {
            const envelope = data as EventEnvelope;
            // Validate mission scoping - no cross-mission leak
            if (envelope.mission_id !== this.missionId) {
              // Drop events for other missions
              return;
            }
            // Update last_event_id persistence
            this.sessionLastEventId = envelope.id;
            this.lastEventId = envelope.id;
            this.onEvent(envelope);
            return;
          }

          // Unknown message
          this.onError?.("invalid_message_type", `Unknown message type: ${data.type}`);
        };

        ws.onerror = () => {
          if (authTimeout) clearTimeout(authTimeout);
          // Error will be followed by onclose
        };

        ws.onclose = (ev) => {
          if (authTimeout) clearTimeout(authTimeout);
          this.clearHeartbeat();
          this.setState("CLOSED");

          if (this.isManuallyClosed || !this.shouldReconnect) {
            return;
          }

          // Bounded exponential backoff reconnect
          const delay = this.getBackoffDelay();
          this.reconnectAttempts += 1;

          // Avoid tight loops - max delay enforced
          if (this.reconnectAttempts > 10) {
            this.onError?.("reconnect_limit", "Max reconnect attempts reached");
            return;
          }

          this.reconnectTimer = setTimeout(() => {
            this.connect().catch(() => {
              // will retry via onclose
            });
          }, delay);
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  disconnect() {
    this.isManuallyClosed = true;
    this.shouldReconnect = false;
    this.clearTimers();
    this.clearHeartbeat();

    if (this.ws) {
      try {
        this.ws.close(1000);
      } catch {
        // ignore
      }
      this.ws = null;
    }
    this.setState("CLOSED");
  }

  getLastEventId(): string | null {
    return this.sessionLastEventId || this.lastEventId;
  }

  getState(): WSConnectionState {
    return this.state;
  }

  isConnected(): boolean {
    return this.state === "SUBSCRIBED" || this.state === "AUTHENTICATED";
  }

  // For testing - simulate event
  _testInjectEvent(envelope: EventEnvelope) {
    this.onEvent(envelope);
  }
}

// Factory for easy creation
export function createWebSocketClient(options: WSClientOptions): RealtimeWebSocketClient {
  return new RealtimeWebSocketClient(options);
}
