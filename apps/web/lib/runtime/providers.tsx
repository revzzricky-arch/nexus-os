"use client";

/**
 * Runtime Providers - Phase 2B-5
 *
 * Keep Phase 2A mock usable, introduce source boundary
 * MockRuntimeProvider vs RealtimeRuntimeProvider same store shape
 * UI agnostic mock/REST/WS, do not remove mock yet
 * Runtime mode mock/realtime, default safe mock
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

// Mock provider - preserves Phase 2A behavior
function useMockProvider() {
  const [isConnected] = useState(false);
  const [connectionState] = useState<WSConnectionState>("CLOSED");
  const [lastEventId] = useState<string | null>(null);
  const [error] = useState<string | null>(null);

  const connect = useCallback(async () => {
    // Mock does not connect
  }, []);

  const disconnect = useCallback(() => {
    // Mock does not disconnect
  }, []);

  return { isConnected, connectionState, lastEventId, error, connect, disconnect };
}

// Realtime provider
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
      const token = process.env.NEXT_PUBLIC_NEXUS_TOKEN || "dev-token-change-me";

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
          // No token logging
          if (code === "auth_error" || code === "auth_invalid_token") {
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

  // Select provider based on mode
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

// Hook for easy mode switching - for future UI toggle
export function useRuntimeMode() {
  const { mode, setMode } = useRuntime();
  return { mode, setMode, isMock: mode === "mock", isRealtime: mode === "realtime" };
}
