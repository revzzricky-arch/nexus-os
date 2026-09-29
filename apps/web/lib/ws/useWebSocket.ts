"use client";

import { useEffect, useRef, useState } from "react";

// Phase 3: WS hook matching backend contract mission_id + last_event_id
// Per security: Do NOT use ?token=SECRET in URL
// Chosen approach: Initial auth message after connection
// Shared contract fixed: backend uses mission_id, not channels[]

interface UseWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
  missionId?: string;
  lastEventId?: string;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const wsUrl = options.url || process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
  const [isConnected, setIsConnected] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!options.autoConnect) return;

    // Connect without token in URL - per security requirement
    const ws = new WebSocket(`${wsUrl}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      // Send auth as first message, NOT in URL query
      ws.send(
        JSON.stringify({
          type: "auth",
          token: "Bearer dev-token-scaffold",
        })
      );
      // Subscribe using mission_id (backend contract) - not channels[]
      if (options.missionId) {
        ws.send(
          JSON.stringify({
            type: "subscribe",
            mission_id: options.missionId,
            last_event_id: options.lastEventId,
          })
        );
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setEvents((prev) => [...prev.slice(-100), data]); // keep last 100
      } catch {}
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    ws.onerror = () => {
      setIsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [wsUrl, options.autoConnect, options.missionId, options.lastEventId]);

  return {
    isConnected,
    events,
    ws: wsRef.current,
  };
}
