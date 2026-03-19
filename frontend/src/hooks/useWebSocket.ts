import { useCallback, useEffect, useRef, useState } from 'react';
import type { WSMessage } from '../types/simulation';

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8001';

export function useWebSocket(sessionId: string | null, participantId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<WSMessage[]>([]);

  useEffect(() => {
    if (!sessionId || !participantId) return;

    const ws = new WebSocket(`${WS_BASE}/api/ws/simulation/${sessionId}/${participantId}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);
        setMessages((prev) => [...prev, data]);
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [sessionId, participantId]);

  const sendMessage = useCallback(
    (content: string, targetRole: string = 'broadcast') => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({ type: 'message', content, target_role: targetRole })
        );
      }
    },
    []
  );

  const sendCommand = useCallback((action: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'command', action }));
    }
  }, []);

  return { connected, messages, sendMessage, sendCommand };
}
