import { useEffect, useRef, useState } from 'react';
import type { AgentRole, SimulationMessage } from '../types/simulation';
import { ROLE_COLORS, ROLE_DISPLAY_NAMES } from '../types/simulation';

const DEPARTMENT_ROLES: AgentRole[] = ['soumu', 'shoubou', 'kensetsu', 'fukushi'];

// Information source styling
const SOURCE_STYLE: Record<string, { icon: string; color: string }> = {
  '住民': { icon: '🏠', color: '#0891B2' },
  '警察': { icon: '🚔', color: '#1E40AF' },
  '警察(110番)': { icon: '🚔', color: '#1E40AF' },
  '消防': { icon: '🚒', color: '#EA580C' },
  '消防(119番)': { icon: '🚒', color: '#EA580C' },
  '気象台': { icon: '🌧', color: '#0284C7' },
  '報道': { icon: '📺', color: '#6B7280' },
  '市町村': { icon: '🏛', color: '#2563EB' },
  '県': { icon: '🏛', color: '#7C3AED' },
  '自衛隊': { icon: '🪖', color: '#064E3B' },
};

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
    // Match by sender role, responsible department, or direct name
    if (m.sender === activeChannel) return true;
    // Match by responsible department
    const deptName = ROLE_DISPLAY_NAMES[activeChannel as AgentRole]?.[0];
    if (deptName && m.responsible_department === deptName) return true;
    return false;
  });

  // Count unread per channel (messages since last view)
  const countByDept: Record<string, number> = {};
  for (const msg of messages) {
    if (msg.responsible_department) {
      const roleKey = Object.entries(ROLE_DISPLAY_NAMES).find(
        ([, v]) => v[0] === msg.responsible_department
      )?.[0];
      if (roleKey) {
        countByDept[roleKey] = (countByDept[roleKey] || 0) + 1;
      }
    }
  }

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
        {channels.map((ch) => {
          const count = ch.id === 'all' ? messages.length : (countByDept[ch.id] || 0);
          return (
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
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              {ch.name}
              {count > 0 && (
                <span style={{
                  fontSize: 10, minWidth: 18, textAlign: 'center',
                  padding: '0 4px', borderRadius: 10,
                  background: activeChannel === ch.id ? ch.color : '#E5E7EB',
                  color: activeChannel === ch.id ? 'white' : '#666',
                }}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {filteredMessages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40, fontSize: 13 }}>
            状況付与を待機中...
          </div>
        )}
        {filteredMessages.map((msg, i) => (
          <ChatBubble key={i} msg={msg} />
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

/* ─── Individual Chat Bubble ─── */

function ChatBubble({ msg }: { msg: SimulationMessage }) {
  const source = msg.source || '';
  const srcStyle = SOURCE_STYLE[source];
  const isInjection = !!msg.related_event_id && !!source;
  const isSystem = msg.message_type === 'system';
  const isHint = msg.message_type === 'hint';
  const isAlert = msg.message_type === 'alert';
  const senderColor = srcStyle?.color || ROLE_COLORS[msg.sender] || '#374151';

  if (isSystem) {
    return (
      <div style={{ textAlign: 'center', margin: '8px 0', fontSize: 12, color: '#9CA3AF' }}>
        {msg.content}
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 14 }}>
      {/* Header: source/sender + time + badges */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        {/* Source icon + name */}
        {isInjection && srcStyle ? (
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 3,
            fontWeight: 'bold', fontSize: 13, color: senderColor,
          }}>
            <span style={{ fontSize: 14 }}>{srcStyle.icon}</span>
            {source}
          </span>
        ) : (
          <span style={{ fontWeight: 'bold', color: senderColor, fontSize: 13 }}>
            {msg.sender_name}
          </span>
        )}

        {/* Responsible department badge */}
        {msg.responsible_department && (
          <>
            <span style={{ color: '#D1D5DB', fontSize: 11 }}>→</span>
            <span style={{
              fontSize: 10, padding: '1px 6px', borderRadius: 4,
              background: '#DBEAFE', color: '#1E40AF', fontWeight: 500,
            }}>
              {msg.responsible_department}
            </span>
          </>
        )}

        {/* Time */}
        {msg.sim_time && (
          <span style={{ fontSize: 11, color: '#9CA3AF', fontFamily: 'monospace' }}>
            {msg.sim_time}
          </span>
        )}

        {/* Badges */}
        {isHint && (
          <span style={{
            fontSize: 10, background: '#FEF3C7', color: '#92400E',
            padding: '1px 6px', borderRadius: 8,
          }}>
            ヒント
          </span>
        )}
        {isAlert && (
          <span style={{
            fontSize: 10, background: '#FEE2E2', color: '#991B1B',
            padding: '1px 6px', borderRadius: 8,
          }}>
            警報
          </span>
        )}
      </div>

      {/* Message body */}
      <div
        style={{
          padding: '10px 14px',
          borderRadius: 10,
          borderLeft: `3px solid ${senderColor}`,
          fontSize: 14,
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          background: isInjection
            ? '#FFFBEB' // warm yellow for injected events
            : isAlert
              ? '#FEF2F2'
              : isHint
                ? '#FFFBEB'
                : '#F9FAFB',
          boxShadow: isInjection ? '0 1px 3px rgba(0,0,0,0.06)' : undefined,
        }}
      >
        {msg.content}
      </div>
    </div>
  );
}
