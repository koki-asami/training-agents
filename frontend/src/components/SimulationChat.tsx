import { useEffect, useRef, useState } from 'react';
import type { AgentRole, SimulationMessage } from '../types/simulation';
import { ROLE_COLORS, ROLE_DISPLAY_NAMES } from '../types/simulation';

const DEPARTMENT_ROLES: AgentRole[] = ['soumu', 'shoubou', 'kensetsu', 'fukushi'];

interface Props {
  messages: SimulationMessage[];
  onSendMessage: (content: string, targetRole: string) => void;
}

export function SimulationChat({ messages, onSendMessage }: Props) {
  const [input, setInput] = useState('');
  const [activeChannel, setActiveChannel] = useState<string>('all');
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const filteredMessages = messages.filter((m) => {
    if (activeChannel === 'all') return true;
    return m.sender === activeChannel || m.sender_name === activeChannel;
  });

  const handleSend = () => {
    if (!input.trim()) return;
    const target = activeChannel === 'all' ? 'broadcast' : activeChannel;
    onSendMessage(input.trim(), target);
    setInput('');
  };

  const channels = [
    { id: 'all', name: '全体', color: '#6B7280' },
    ...DEPARTMENT_ROLES.map((r) => ({
      id: r,
      name: ROLE_DISPLAY_NAMES[r]?.[0] || r,
      color: ROLE_COLORS[r] || '#666',
    })),
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Channel tabs */}
      <div
        style={{
          display: 'flex',
          gap: 4,
          padding: '8px 8px 0',
          borderBottom: '1px solid #e5e7eb',
          overflowX: 'auto',
        }}
      >
        {channels.map((ch) => (
          <button
            key={ch.id}
            onClick={() => setActiveChannel(ch.id)}
            style={{
              padding: '6px 12px',
              border: 'none',
              borderBottom: `2px solid ${activeChannel === ch.id ? ch.color : 'transparent'}`,
              background: 'none',
              cursor: 'pointer',
              fontWeight: activeChannel === ch.id ? 'bold' : 'normal',
              color: activeChannel === ch.id ? ch.color : '#666',
              fontSize: 13,
              whiteSpace: 'nowrap',
            }}
          >
            {ch.name}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {filteredMessages.map((msg, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
              <span
                style={{
                  fontWeight: 'bold',
                  color: ROLE_COLORS[msg.sender] || '#333',
                  fontSize: 13,
                }}
              >
                {msg.sender_name}
              </span>
              {msg.sim_time && (
                <span style={{ fontSize: 11, color: '#999' }}>[{msg.sim_time}]</span>
              )}
              {msg.message_type === 'hint' && (
                <span
                  style={{
                    fontSize: 10,
                    background: '#FEF3C7',
                    color: '#92400E',
                    padding: '1px 6px',
                    borderRadius: 8,
                  }}
                >
                  ヒント
                </span>
              )}
            </div>
            <div
              style={{
                padding: '8px 12px',
                background: msg.message_type === 'alert' ? '#FEF2F2' : '#F9FAFB',
                borderRadius: 8,
                borderLeft: `3px solid ${ROLE_COLORS[msg.sender] || '#ccc'}`,
                fontSize: 14,
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
              }}
            >
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div style={{ display: 'flex', gap: 8, padding: 12, borderTop: '1px solid #e5e7eb' }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder={
            activeChannel === 'all'
              ? '全部署に指示を入力...'
              : `${channels.find((c) => c.id === activeChannel)?.name || ''}に指示を入力...`
          }
          style={{
            flex: 1,
            padding: '8px 12px',
            border: '1px solid #D1D5DB',
            borderRadius: 6,
            fontSize: 14,
          }}
        />
        <button
          onClick={handleSend}
          style={{
            padding: '8px 20px',
            background: '#DC2626',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            cursor: 'pointer',
            fontWeight: 'bold',
          }}
        >
          送信
        </button>
      </div>
    </div>
  );
}
