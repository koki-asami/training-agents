import { useEffect, useState } from 'react';
import type { DisasterStateSummary, SessionInfo, SimulationMessage } from '../types/simulation';
import { useWebSocket } from '../hooks/useWebSocket';
import { SimulationChat } from './SimulationChat';
import { StatusPanel } from './StatusPanel';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8002';

// seconds_per_sim_minute: how many real seconds = 1 minute of scenario time
const SPEED_OPTIONS = [
  { label: '高速 (2秒/分)', value: 2 },
  { label: '速い (4秒/分)', value: 4 },
  { label: '標準 (8秒/分)', value: 8 },
  { label: 'ゆっくり (15秒/分)', value: 15 },
  { label: '超低速 (30秒/分)', value: 30 },
];

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
  const [paused, setPaused] = useState(false);
  const [timeScale, setTimeScale] = useState(8);

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

  const apiCall = async (path: string, method = 'POST') => {
    try {
      await fetch(`${API_BASE}/api/sessions/${sessionInfo.session_id}${path}`, { method });
    } catch (e) {
      console.error(`API call failed: ${path}`, e);
    }
  };

  const handleStart = async () => {
    await apiCall('/start');
    setStarted(true);
  };

  const handlePause = async () => {
    await apiCall('/pause');
    setPaused(true);
  };

  const handleResume = async () => {
    await apiCall('/resume');
    setPaused(false);
  };

  const handleSpeedChange = async (secondsPerMin: number) => {
    setTimeScale(secondsPerMin);
    try {
      await fetch(
        `${API_BASE}/api/sessions/${sessionInfo.session_id}/interval?seconds=${secondsPerMin}`,
        { method: 'POST' }
      );
    } catch (e) {
      console.error('Failed to set speed', e);
    }
  };

  const handleStop = async () => {
    await apiCall('/stop');
    setStarted(false);
    setPaused(false);
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
          <a
            href={`/admin/${sessionInfo.session_id}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 11, color: '#9CA3AF', textDecoration: 'underline' }}
          >
            管理画面
          </a>
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
          {paused && (
            <span
              style={{
                fontSize: 11,
                padding: '2px 8px',
                borderRadius: 8,
                background: '#CA8A04',
              }}
            >
              一時停止中
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* Simulation time */}
          {simTime && (
            <span style={{ fontFamily: 'monospace', fontSize: 18 }}>訓練時刻 {simTime}</span>
          )}

          {/* Speed control */}
          {started && (
            <select
              value={timeScale}
              onChange={(e) => handleSpeedChange(Number(e.target.value))}
              style={{
                padding: '4px 8px',
                borderRadius: 4,
                border: '1px solid #4B5563',
                background: '#374151',
                color: 'white',
                fontSize: 12,
              }}
            >
              {SPEED_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}

          {/* Control buttons */}
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
            <>
              {paused ? (
                <button
                  onClick={handleResume}
                  style={{
                    padding: '6px 16px',
                    background: '#22C55E',
                    color: 'white',
                    border: 'none',
                    borderRadius: 4,
                    cursor: 'pointer',
                    fontWeight: 'bold',
                  }}
                >
                  再開
                </button>
              ) : (
                <button
                  onClick={handlePause}
                  style={{
                    padding: '6px 16px',
                    background: '#CA8A04',
                    color: 'white',
                    border: 'none',
                    borderRadius: 4,
                    cursor: 'pointer',
                    fontWeight: 'bold',
                  }}
                >
                  一時停止
                </button>
              )}
              <button
                onClick={handleStop}
                style={{
                  padding: '6px 16px',
                  background: '#6B7280',
                  color: 'white',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontSize: 12,
                }}
              >
                終了
              </button>
            </>
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
