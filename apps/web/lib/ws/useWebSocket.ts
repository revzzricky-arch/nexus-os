"use client";

import { useEffect, useRef, useState } from "react";

// Scaffold WS hook - placeholder, no real streaming yet
// Per security: Do NOT use ?token=SECRET in URL
// Chosen approach: Initial auth message after connection

interface UseWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
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
      // For scaffold, use placeholder token
      ws.send(
        JSON.stringify({
          type: "auth",
          token: "Bearer dev-token-scaffold",
        })
      );
      // Subscribe to channels
      ws.send(
        JSON.stringify({
          type: "subscribe",
          channels: ["mission:scaffold", "approvals"],
        })
      );
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
  }, [wsUrl, options.autoConnect]);

  return {
    isConnected,
    events,
    ws: wsRef.current,
  };
}
