import { useEffect, useState } from 'react';
import type { DisasterStateSummary, SessionInfo, SimulationMessage } from '../types/simulation';
import { useWebSocket } from '../hooks/useWebSocket';
import { SimulationChat } from './SimulationChat';
import { StatusPanel } from './StatusPanel';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Props {
  sessionInfo: SessionInfo;
  participantId: string;
}

export function Dashboard({ sessionInfo, participantId }: Props) {
  const { connected, messages, sendMessage, sendCommand } = useWebSocket(
    sessionInfo.session_id,
    participantId
  );
  const [state, setState] = useState<DisasterStateSummary | null>(null);
  const [chatMessages, setChatMessages] = useState<SimulationMessage[]>([]);
  const [simTime, setSimTime] = useState('');
  const [started, setStarted] = useState(false);

  // Process incoming WebSocket messages
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (!last) return;

    if (last.type === 'state_update') {
      setState(last.state);
      setSimTime(last.state.sim_time);
    } else if (last.type === 'message') {
      setChatMessages((prev) => [...prev, last as SimulationMessage]);
    } else if (last.type === 'system') {
      // Show system messages in chat
      setChatMessages((prev) => [
        ...prev,
        {
          type: 'message',
          sender: 'system',
          sender_name: 'システム',
          content: last.content,
          sim_time: '',
          message_type: 'system',
        },
      ]);
    }
  }, [messages]);

  const handleStart = async () => {
    try {
      await fetch(`${API_BASE}/api/sessions/${sessionInfo.session_id}/start`, {
        method: 'POST',
      });
      setStarted(true);
    } catch (e) {
      console.error('Failed to start session', e);
    }
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', fontFamily: 'sans-serif' }}>
      {/* Header */}
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          background: '#1F2937',
          color: 'white',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h1 style={{ fontSize: 16, margin: 0 }}>防災訓練シミュレーション</h1>
          <span
            style={{
              fontSize: 11,
              padding: '2px 8px',
              borderRadius: 8,
              background: connected ? '#22C55E' : '#EF4444',
            }}
          >
            {connected ? '接続中' : '未接続'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {simTime && (
            <span style={{ fontFamily: 'monospace', fontSize: 18 }}>訓練時刻 {simTime}</span>
          )}
          {!started ? (
            <button
              onClick={handleStart}
              disabled={!connected}
              style={{
                padding: '6px 16px',
                background: connected ? '#DC2626' : '#6B7280',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                cursor: connected ? 'pointer' : 'not-allowed',
                fontWeight: 'bold',
              }}
            >
              訓練開始
            </button>
          ) : (
            <button
              onClick={() => sendCommand('pause')}
              style={{
                padding: '6px 16px',
                background: '#CA8A04',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                cursor: 'pointer',
              }}
            >
              一時停止
            </button>
          )}
        </div>
      </header>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left: Chat (70%) */}
        <div style={{ flex: 7, borderRight: '1px solid #E5E7EB', display: 'flex', flexDirection: 'column' }}>
          <SimulationChat messages={chatMessages} onSendMessage={sendMessage} />
        </div>

        {/* Right: Status Panel (30%) */}
        <div style={{ flex: 3, overflowY: 'auto', background: '#FAFAFA' }}>
          <StatusPanel state={state} simTime={simTime} />
        </div>
      </div>
    </div>
  );
}
