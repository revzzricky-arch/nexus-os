"use client";

/**
 * Runtime Providers - Phase 2B-5 Hardened
 *
 * Keep Phase 2A mock usable, introduce source boundary
 * MockRuntimeProvider vs RealtimeRuntimeProvider same store shape
 * UI agnostic mock/REST/WS, do not remove mock yet
 * Runtime mode mock/realtime, default safe mock
 *
 * Security hardening:
 * - No default credential embedded in browser bundle
 * - Realtime mode requires explicit NEXT_PUBLIC_NEXUS_TOKEN or manual runtime config
 * - Mock mode works without token
 * - No token logging, no token in URL, token only in first auth message
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import { RealtimeWebSocketClient } from "./websocket-client";
import { runtimeEventAdapter } from "./event-adapter";
import type { RuntimeMode, EventEnvelope, WSConnectionState } from "./types";
import { useRuntimeStore } from "@/lib/store/runtime";

interface RuntimeContextValue {
  mode: RuntimeMode;
  isConnected: boolean;
  connectionState: WSConnectionState;
  lastEventId: string | null;
  error: string | null;
  connect: (missionId?: string) => Promise<void>;
  disconnect: () => void;
  setMode: (mode: RuntimeMode) => void;
}

const RuntimeContext = createContext<RuntimeContextValue>({
  mode: "mock",
  isConnected: false,
  connectionState: "CLOSED",
  lastEventId: null,
  error: null,
  connect: async () => {},
  disconnect: () => {},
  setMode: () => {},
});

export function useRuntime() {
  return useContext(RuntimeContext);
}

// Mock provider - preserves Phase 2A behavior, works without token
function useMockProvider() {
  const [isConnected] = useState(false);
  const [connectionState] = useState<WSConnectionState>("CLOSED");
  const [lastEventId] = useState<string | null>(null);
  const [error] = useState<string | null>(null);

  const connect = useCallback(async () => {
    // Mock does not connect, no token required
  }, []);

  const disconnect = useCallback(() => {
    // Mock does not disconnect
  }, []);

  return { isConnected, connectionState, lastEventId, error, connect, disconnect };
}

// Helper to get token via explicit configuration only, no default fallback
function getRealtimeToken(): string | null {
  // 1. Env var - explicit configuration required for realtime
  const envToken = process.env.NEXT_PUBLIC_NEXUS_TOKEN;
  if (envToken && envToken.trim()) {
    return envToken.trim();
  }

  // 2. Manual runtime config mechanism - window.__NEXUS_RUNTIME_CONFIG__.token
  // Allows developer to set token via console or runtime config without embedding default
  // Example: window.__NEXUS_RUNTIME_CONFIG__ = { token: "your-dev-token" }
  // Or localStorage manual: localStorage.setItem('nexus_realtime_token', '...')
  if (typeof window !== "undefined") {
    try {
      const runtimeConfig = (window as any).__NEXUS_RUNTIME_CONFIG__;
      if (runtimeConfig && runtimeConfig.token && typeof runtimeConfig.token === "string" && runtimeConfig.token.trim()) {
        return runtimeConfig.token.trim();
      }
      // Optional localStorage for manual dev configuration (explicit, not default)
      const lsToken = window.localStorage?.getItem("nexus_realtime_token");
      if (lsToken && lsToken.trim()) {
        return lsToken.trim();
      }
    } catch {
      // Ignore errors accessing window/localStorage
    }
  }

  // No token - no default credential embedded
  return null;
}

// Realtime provider - requires explicit token
function useRealtimeProvider(initialMissionId?: string) {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState<WSConnectionState>("CLOSED");
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const clientRef = useRef<RealtimeWebSocketClient | null>(null);
  const missionIdRef = useRef<string | null>(initialMissionId || null);

  const connect = useCallback(
    async (missionId?: string) => {
      const targetMissionId = missionId || missionIdRef.current || useRuntimeStore.getState().activeMission?.id;
      if (!targetMissionId) {
        setError("No mission ID for realtime connection");
        return;
      }

      missionIdRef.current = targetMissionId;

      // Disconnect existing
      if (clientRef.current) {
        clientRef.current.disconnect();
      }

      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
      const apiUrl = `${wsUrl}/api/v1/ws`;

      // Explicit token required - no default fallback
      const token = getRealtimeToken();
      if (!token) {
        setError(
          "Realtime mode requires explicit token: set NEXT_PUBLIC_NEXUS_TOKEN env var or window.__NEXUS_RUNTIME_CONFIG__={token:...} or localStorage nexus_realtime_token. No default credential embedded."
        );
        return;
      }

      // Token is sent only in first auth message, never in URL (enforced in websocket-client.ts)
      const client = new RealtimeWebSocketClient({
        url: apiUrl,
        token,
        missionId: targetMissionId,
        lastEventId: clientRef.current?.getLastEventId() || null,
        onEvent: (envelope: EventEnvelope) => {
          setLastEventId(envelope.id);
          runtimeEventAdapter.dispatch(envelope);
        },
        onStateChange: (state) => {
          setConnectionState(state);
          setIsConnected(state === "SUBSCRIBED" || state === "AUTHENTICATED");
        },
        onError: (code, message) => {
          // No token logging - do not include token in error messages
          if (code === "auth_error" || code === "auth_invalid_token" || code === "auth_missing_token") {
            setError(`Auth failed: ${code}`);
          } else {
            setError(`${code}: ${message}`);
          }
        },
        onSubscribed: (mid, replayCount) => {
          setError(null);
        },
      });

      clientRef.current = client;

      try {
        await client.connect();
      } catch (e: any) {
        // Do not log token
        setError(e.message || "Connection failed");
      }
    },
    []
  );

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
    setIsConnected(false);
    setConnectionState("CLOSED");
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return { isConnected, connectionState, lastEventId, error, connect, disconnect };
}

export function RuntimeProvider({
  children,
  defaultMode = "mock",
  initialMissionId,
}: {
  children: React.ReactNode;
  defaultMode?: RuntimeMode;
  initialMissionId?: string;
}) {
  const [mode, setMode] = useState<RuntimeMode>(defaultMode);

  const mock = useMockProvider();
  const realtime = useRealtimeProvider(initialMissionId);

  const active = mode === "realtime" ? realtime : mock;

  const contextValue: RuntimeContextValue = {
    mode,
    isConnected: active.isConnected,
    connectionState: active.connectionState,
    lastEventId: active.lastEventId,
    error: active.error,
    connect: active.connect,
    disconnect: active.disconnect,
    setMode,
  };

  return <RuntimeContext.Provider value={contextValue}>{children}</RuntimeContext.Provider>;
}

export function useRuntimeMode() {
  const { mode, setMode } = useRuntime();
  return { mode, setMode, isMock: mode === "mock", isRealtime: mode === "realtime" };
}

// Export helper for testing - proves no default credential
export function __test_getRealtimeToken(): string | null {
  return getRealtimeToken();
}
