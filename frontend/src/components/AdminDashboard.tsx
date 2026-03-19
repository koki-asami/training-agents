import { useCallback, useEffect, useRef, useState } from 'react';
import { ROLE_COLORS, ROLE_DISPLAY_NAMES } from '../types/simulation';
import type { DisasterStateSummary } from '../types/simulation';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

interface TimelineEvent {
  type: 'event';
  event_id: string;
  sim_time: string;
  title: string;
  source: string;
  target_agent: string;
  target_agent_name: string;
  content_trainee: string;
  content_admin: string;
  expected_actions: string;
  expected_issues: string;
  training_objective: string;
  weather_info: string;
  river_info: string;
  terrain_info: string;
  water_level_status: string;
  secondary_disaster_risks: string;
  injected: boolean;
  injected_at: string | null;
  response_received: boolean;
  response_at: string | null;
  score: number | null;
  score_notes: string | null;
  response_time_minutes: number | null;
  action_taken: string | null;
}

interface TimelineMessage {
  type: 'message';
  message_id: string;
  sim_time: string;
  timestamp: string;
  sender: string;
  sender_name: string;
  receiver: string;
  content: string;
  message_type: string;
  related_event_id: string | null;
}

interface TaskItem {
  task_id: string;
  event_id: string;
  title: string;
  description: string;
  responsible_role: string;
  status: string;
  priority: string;
  sim_time_created: string;
  sim_time_completed: string | null;
  assigned_to: string;
  notes: string;
  score: number | null;
}

interface TaskSummary {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  by_role: Record<string, number>;
  completion_rate: number;
}

interface TimelineData {
  session_id: string;
  municipality: string;
  training_level: string;
  difficulty: string;
  phase: string;
  current_sim_time: string;
  total_events: number;
  injected_events: number;
  responded_events: number;
  events: TimelineEvent[];
  messages: TimelineMessage[];
  tasks: TaskItem[];
  task_summary: TaskSummary;
  state_summary: DisasterStateSummary;
}

interface Props {
  sessionId: string;
}

export function AdminDashboard({ sessionId }: Props) {
  const [data, setData] = useState<TimelineData | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
  const [viewMode, setViewMode] = useState<'timeline' | 'tasks' | 'messages'>('timeline');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState('');
  const intervalRef = useRef<number | null>(null);

  const fetchTimeline = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/timeline`);
      if (res.status === 404) {
        setError('セッションが見つかりません。サーバー再起動によりセッションが消失した可能性があります。新しいセッションを作成してください。');
        setAutoRefresh(false);
        return;
      }
      if (!res.ok) throw new Error('Failed to fetch timeline');
      const json = await res.json();
      setData(json);
      setError('');
    } catch (e: any) {
      setError(e.message);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchTimeline();
    if (autoRefresh) {
      intervalRef.current = window.setInterval(fetchTimeline, 3000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchTimeline, autoRefresh]);

  if (!data) {
    return (
      <div style={{ padding: 40, textAlign: 'center', fontFamily: 'sans-serif' }}>
        {error ? (
          <div>
            <div style={{ color: 'red', marginBottom: 16 }}>{error}</div>
            <a href="/" style={{ color: '#2563EB' }}>セッション作成画面に戻る</a>
          </div>
        ) : '読み込み中...'}
      </div>
    );
  }

  const progressPct = data.total_events > 0
    ? Math.round((data.injected_events / data.total_events) * 100)
    : 0;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', fontFamily: 'sans-serif' }}>
      {/* Header */}
      <header style={{ background: '#111827', color: 'white', padding: '10px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h1 style={{ fontSize: 16, margin: 0 }}>管理者ダッシュボード</h1>
            <span style={{ fontSize: 12, color: '#9CA3AF' }}>
              {data.municipality} / {data.training_level} / {data.difficulty}
            </span>
            <span
              style={{
                fontSize: 11,
                padding: '2px 8px',
                borderRadius: 8,
                background: data.phase === 'running' ? '#22C55E' : data.phase === 'paused' ? '#CA8A04' : '#6B7280',
              }}
            >
              {data.phase === 'running' ? '進行中' : data.phase === 'paused' ? '一時停止' : data.phase === 'completed' ? '完了' : '準備中'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontFamily: 'monospace', fontSize: 20 }}>
              {data.current_sim_time}
            </span>
            <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              自動更新
            </label>
            <button
              onClick={fetchTimeline}
              style={{ padding: '4px 12px', background: '#374151', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}
            >
              更新
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ flex: 1, height: 6, background: '#374151', borderRadius: 3, overflow: 'hidden' }}>
            <div
              style={{
                width: `${progressPct}%`,
                height: '100%',
                background: '#3B82F6',
                transition: 'width 0.3s',
              }}
            />
          </div>
          <span style={{ fontSize: 11, color: '#9CA3AF', whiteSpace: 'nowrap' }}>
            {data.injected_events}/{data.total_events} イベント ({progressPct}%)
            | 応答 {data.responded_events}
          </span>
        </div>
      </header>

      {/* Tab bar */}
      <div style={{ display: 'flex', background: '#F3F4F6', borderBottom: '1px solid #E5E7EB' }}>
        {([
          { key: 'timeline' as const, label: 'イベントタイムライン' },
          { key: 'tasks' as const, label: `タスク一覧 (${data.task_summary?.total || 0})` },
          { key: 'messages' as const, label: 'メッセージログ' },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setViewMode(key)}
            style={{
              padding: '8px 20px',
              border: 'none',
              borderBottom: `2px solid ${viewMode === key ? '#3B82F6' : 'transparent'}`,
              background: 'none',
              cursor: 'pointer',
              fontWeight: viewMode === key ? 'bold' : 'normal',
              color: viewMode === key ? '#1F2937' : '#6B7280',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left: timeline/messages list */}
        <div style={{ flex: 6, overflowY: 'auto', padding: 0 }}>
          {viewMode === 'timeline' ? (
            <EventTimeline
              events={data.events}
              selectedEvent={selectedEvent}
              onSelect={setSelectedEvent}
            />
          ) : viewMode === 'tasks' ? (
            <TaskBoard
              tasks={data.tasks}
              summary={data.task_summary}
              sessionId={sessionId}
              onRefresh={fetchTimeline}
            />
          ) : (
            <MessageLog messages={data.messages} />
          )}
        </div>

        {/* Right: detail panel */}
        <div style={{ flex: 4, overflowY: 'auto', borderLeft: '1px solid #E5E7EB', background: '#FAFAFA' }}>
          {selectedEvent ? (
            <EventDetail
              event={selectedEvent}
              messages={data.messages.filter((m) => m.related_event_id === selectedEvent.event_id)}
            />
          ) : (
            <StateSummary state={data.state_summary} />
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Event Timeline ─── */

function EventTimeline({
  events,
  selectedEvent,
  onSelect,
}: {
  events: TimelineEvent[];
  selectedEvent: TimelineEvent | null;
  onSelect: (e: TimelineEvent) => void;
}) {
  // Group events by sim_time
  const groups: { time: string; events: TimelineEvent[] }[] = [];
  let lastTime = '';
  for (const e of events) {
    if (e.sim_time !== lastTime) {
      groups.push({ time: e.sim_time, events: [e] });
      lastTime = e.sim_time;
    } else {
      groups[groups.length - 1].events.push(e);
    }
  }

  return (
    <div style={{ padding: '0 0 20px' }}>
      {groups.map((group) => (
        <div key={group.time}>
          {/* Time header */}
          <div
            style={{
              position: 'sticky',
              top: 0,
              background: '#F9FAFB',
              padding: '6px 16px',
              fontSize: 12,
              fontWeight: 'bold',
              color: '#6B7280',
              borderBottom: '1px solid #E5E7EB',
              zIndex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <span style={{ fontFamily: 'monospace', fontSize: 14, color: '#1F2937' }}>
              {group.time}
            </span>
            {group.events[0].weather_info && (
              <span style={{ fontSize: 11, color: '#0284C7', maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {group.events[0].weather_info.substring(0, 60)}
              </span>
            )}
          </div>

          {/* Events in this time group */}
          {group.events.map((event) => {
            const isSelected = selectedEvent?.event_id === event.event_id;
            return (
              <div
                key={event.event_id}
                onClick={() => onSelect(event)}
                style={{
                  display: 'flex',
                  padding: '10px 16px',
                  cursor: 'pointer',
                  background: isSelected ? '#EFF6FF' : 'white',
                  borderBottom: '1px solid #F3F4F6',
                  borderLeft: `4px solid ${getStatusColor(event)}`,
                  gap: 12,
                  alignItems: 'flex-start',
                  transition: 'background 0.1s',
                }}
              >
                {/* Status indicator */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 50, gap: 2 }}>
                  <span style={{ fontSize: 11, fontWeight: 'bold', color: '#6B7280' }}>
                    #{event.event_id}
                  </span>
                  <StatusBadge event={event} />
                </div>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                    <span style={{ fontWeight: 'bold', fontSize: 14 }}>{event.title}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 8, fontSize: 12, color: '#6B7280' }}>
                    <span
                      style={{
                        padding: '1px 6px',
                        borderRadius: 4,
                        background: ROLE_COLORS[event.target_agent] + '20',
                        color: ROLE_COLORS[event.target_agent] || '#666',
                        fontSize: 11,
                      }}
                    >
                      {event.target_agent_name}
                    </span>
                    <span>情報源: {event.source}</span>
                    {event.score !== null && (
                      <span style={{ color: event.score >= 4 ? '#15803D' : event.score <= 2 ? '#DC2626' : '#CA8A04' }}>
                        スコア: {event.score}/5
                      </span>
                    )}
                    {event.response_time_minutes !== null && (
                      <span>応答: {event.response_time_minutes.toFixed(1)}分</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ event }: { event: TimelineEvent }) {
  if (event.response_received) {
    return (
      <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 8, background: '#DCFCE7', color: '#15803D' }}>
        応答済
      </span>
    );
  }
  if (event.injected) {
    return (
      <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 8, background: '#FEF9C3', color: '#92400E' }}>
        付与済
      </span>
    );
  }
  return (
    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 8, background: '#F3F4F6', color: '#6B7280' }}>
      待機中
    </span>
  );
}

function getStatusColor(event: TimelineEvent): string {
  if (event.score !== null) {
    if (event.score >= 4) return '#22C55E';
    if (event.score <= 2) return '#EF4444';
    return '#F59E0B';
  }
  if (event.response_received) return '#22C55E';
  if (event.injected) return '#F59E0B';
  return '#D1D5DB';
}

/* ─── Event Detail Panel ─── */

function EventDetail({
  event,
  messages,
}: {
  event: TimelineEvent;
  messages: TimelineMessage[];
}) {
  return (
    <div style={{ padding: 16, fontSize: 13 }}>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, color: '#6B7280' }}>#{event.event_id} / {event.sim_time}</div>
        <h2 style={{ fontSize: 16, margin: '4px 0' }}>{event.title}</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <StatusBadge event={event} />
          {event.score !== null && (
            <span style={{ fontSize: 11, padding: '1px 6px', borderRadius: 8, background: '#EFF6FF', color: '#2563EB' }}>
              スコア {event.score}/5
            </span>
          )}
        </div>
      </div>

      <DetailSection title="管理用詳細" content={event.content_admin} />
      <DetailSection title="訓練者向け" content={event.content_trainee} />
      <DetailSection title="狙い" content={event.training_objective} />
      <DetailSection title="期待される対応行動" content={event.expected_actions} highlight />
      <DetailSection title="想定される課題" content={event.expected_issues} />
      <DetailSection title="気象情報" content={event.weather_info} />
      <DetailSection title="河川・水位状況" content={`${event.river_info}\n${event.water_level_status}`} />
      <DetailSection title="地形情報" content={event.terrain_info} />
      <DetailSection title="二次災害リスク" content={event.secondary_disaster_risks} />

      {event.action_taken && (
        <DetailSection title="参加者の実際の対応" content={event.action_taken} highlight />
      )}
      {event.score_notes && (
        <DetailSection title="評価コメント" content={event.score_notes} />
      )}

      {/* Related messages */}
      {messages.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 'bold', color: '#6B7280', marginBottom: 4 }}>
            関連メッセージ ({messages.length})
          </div>
          {messages.map((m) => (
            <div
              key={m.message_id}
              style={{
                padding: '6px 8px',
                marginBottom: 4,
                background: '#F9FAFB',
                borderRadius: 4,
                fontSize: 12,
                borderLeft: `3px solid ${ROLE_COLORS[m.sender] || '#ccc'}`,
              }}
            >
              <span style={{ fontWeight: 'bold', color: ROLE_COLORS[m.sender] || '#333' }}>
                {m.sender_name}
              </span>
              <span style={{ color: '#999', marginLeft: 6 }}>[{m.sim_time}]</span>
              <div style={{ marginTop: 2, whiteSpace: 'pre-wrap' }}>
                {m.content.substring(0, 200)}{m.content.length > 200 ? '...' : ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DetailSection({ title, content, highlight }: { title: string; content: string; highlight?: boolean }) {
  if (!content || !content.trim()) return null;
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 11, fontWeight: 'bold', color: '#6B7280', marginBottom: 2 }}>{title}</div>
      <div
        style={{
          fontSize: 13,
          lineHeight: 1.5,
          whiteSpace: 'pre-wrap',
          padding: highlight ? '6px 8px' : 0,
          background: highlight ? '#FEF3C7' : 'transparent',
          borderRadius: highlight ? 4 : 0,
        }}
      >
        {content}
      </div>
    </div>
  );
}

/* ─── Task Board ─── */

const TASK_STATUS_CONFIG: Record<string, { label: string; bg: string; color: string }> = {
  pending: { label: '待機', bg: '#F3F4F6', color: '#6B7280' },
  active: { label: '対応待ち', bg: '#FEF3C7', color: '#92400E' },
  in_progress: { label: '対応中', bg: '#DBEAFE', color: '#1E40AF' },
  completed: { label: '完了', bg: '#DCFCE7', color: '#15803D' },
  overdue: { label: '超過', bg: '#FEE2E2', color: '#991B1B' },
  skipped: { label: 'スキップ', bg: '#F3F4F6', color: '#9CA3AF' },
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  critical: { label: '緊急', color: '#DC2626', icon: '!!' },
  high: { label: '高', color: '#EA580C', icon: '!' },
  medium: { label: '中', color: '#CA8A04', icon: '-' },
  low: { label: '低', color: '#6B7280', icon: '' },
};

function TaskBoard({
  tasks,
  summary,
  sessionId,
  onRefresh,
}: {
  tasks: TaskItem[];
  summary: TaskSummary;
  sessionId: string;
  onRefresh: () => void;
}) {
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterRole, setFilterRole] = useState<string>('');

  const filtered = tasks.filter((t) => {
    if (filterStatus && t.status !== filterStatus) return false;
    if (filterRole && t.responsible_role !== filterRole) return false;
    return true;
  });

  // Sort: overdue first, then active, then by priority
  const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const statusOrder = { overdue: 0, active: 1, in_progress: 2, pending: 3, completed: 4, skipped: 5 };
  const sorted = [...filtered].sort((a, b) => {
    const sa = statusOrder[a.status as keyof typeof statusOrder] ?? 9;
    const sb = statusOrder[b.status as keyof typeof statusOrder] ?? 9;
    if (sa !== sb) return sa - sb;
    const pa = priorityOrder[a.priority as keyof typeof priorityOrder] ?? 9;
    const pb = priorityOrder[b.priority as keyof typeof priorityOrder] ?? 9;
    return pa - pb;
  });

  const handleComplete = async (taskId: string) => {
    await fetch(`${API_BASE}/api/sessions/${sessionId}/tasks/${taskId}/complete`, { method: 'POST' });
    onRefresh();
  };

  return (
    <div>
      {/* Summary bar */}
      <div style={{ display: 'flex', gap: 8, padding: '12px 16px', background: '#F9FAFB', borderBottom: '1px solid #E5E7EB', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ fontWeight: 'bold', fontSize: 13, marginRight: 8 }}>
          進捗: {summary.completion_rate}%
        </div>
        <div style={{ flex: 1, height: 8, background: '#E5E7EB', borderRadius: 4, overflow: 'hidden', minWidth: 100 }}>
          <div style={{ width: `${summary.completion_rate}%`, height: '100%', background: '#22C55E', transition: 'width 0.3s' }} />
        </div>
        {Object.entries(summary.by_status).map(([status, count]) => {
          const cfg = TASK_STATUS_CONFIG[status];
          return (
            <button
              key={status}
              onClick={() => setFilterStatus(filterStatus === status ? '' : status)}
              style={{
                fontSize: 11,
                padding: '2px 8px',
                borderRadius: 8,
                border: filterStatus === status ? '2px solid #3B82F6' : '1px solid transparent',
                background: cfg?.bg || '#F3F4F6',
                color: cfg?.color || '#333',
                cursor: 'pointer',
              }}
            >
              {cfg?.label || status}: {count}
            </button>
          );
        })}
      </div>

      {/* Filter by role */}
      <div style={{ display: 'flex', gap: 4, padding: '8px 16px', borderBottom: '1px solid #F3F4F6', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, color: '#9CA3AF', lineHeight: '24px' }}>部署:</span>
        <button
          onClick={() => setFilterRole('')}
          style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 4, cursor: 'pointer',
            background: !filterRole ? '#3B82F6' : '#F3F4F6',
            color: !filterRole ? 'white' : '#666',
            border: 'none',
          }}
        >
          全て
        </button>
        {Object.entries(summary.by_role).map(([role, count]) => {
          const displayName = ROLE_DISPLAY_NAMES[role as keyof typeof ROLE_DISPLAY_NAMES]?.[0] || role;
          return (
            <button
              key={role}
              onClick={() => setFilterRole(filterRole === role ? '' : role)}
              style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 4, cursor: 'pointer',
                background: filterRole === role ? (ROLE_COLORS[role] || '#3B82F6') : '#F3F4F6',
                color: filterRole === role ? 'white' : ROLE_COLORS[role] || '#666',
                border: 'none',
              }}
            >
              {displayName} ({count})
            </button>
          );
        })}
      </div>

      {/* Task list */}
      <div>
        {sorted.map((task) => {
          const statusCfg = TASK_STATUS_CONFIG[task.status] || TASK_STATUS_CONFIG.pending;
          const priorityCfg = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
          const roleName = ROLE_DISPLAY_NAMES[task.responsible_role as keyof typeof ROLE_DISPLAY_NAMES]?.[0] || task.responsible_role;

          return (
            <div
              key={task.task_id}
              style={{
                display: 'flex',
                padding: '10px 16px',
                borderBottom: '1px solid #F3F4F6',
                gap: 10,
                alignItems: 'center',
                background: task.status === 'overdue' ? '#FEF2F2' : 'white',
              }}
            >
              {/* Priority indicator */}
              <div
                style={{
                  width: 4,
                  height: 36,
                  borderRadius: 2,
                  background: priorityCfg.color,
                  flexShrink: 0,
                }}
              />

              {/* Content */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                  <span style={{ fontSize: 13, fontWeight: task.status === 'active' || task.status === 'overdue' ? 'bold' : 'normal' }}>
                    {task.title}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 6, fontSize: 11, color: '#6B7280', flexWrap: 'wrap' }}>
                  <span style={{ padding: '0 4px', background: statusCfg.bg, color: statusCfg.color, borderRadius: 4 }}>
                    {statusCfg.label}
                  </span>
                  <span style={{ padding: '0 4px', background: priorityCfg.color + '15', color: priorityCfg.color, borderRadius: 4 }}>
                    {priorityCfg.label}
                  </span>
                  <span style={{ color: ROLE_COLORS[task.responsible_role] || '#666' }}>
                    {roleName}
                  </span>
                  <span>#{task.event_id}</span>
                  <span>{task.sim_time_created}</span>
                  {task.notes && (
                    <span style={{ color: '#2563EB' }} title={task.notes}>
                      対応メモあり
                    </span>
                  )}
                </div>
              </div>

              {/* Actions */}
              {(task.status === 'active' || task.status === 'in_progress' || task.status === 'overdue') && (
                <button
                  onClick={() => handleComplete(task.task_id)}
                  style={{
                    padding: '4px 10px',
                    fontSize: 11,
                    border: '1px solid #D1D5DB',
                    borderRadius: 4,
                    background: 'white',
                    cursor: 'pointer',
                    color: '#15803D',
                    flexShrink: 0,
                  }}
                >
                  完了
                </button>
              )}
              {task.status === 'completed' && (
                <span style={{ fontSize: 16, color: '#22C55E', flexShrink: 0 }}>✓</span>
              )}
            </div>
          );
        })}
        {sorted.length === 0 && (
          <div style={{ padding: 40, textAlign: 'center', color: '#9CA3AF' }}>
            {tasks.length === 0 ? 'タスクがまだありません（訓練開始後に生成されます）' : 'フィルター条件に一致するタスクがありません'}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Message Log ─── */

function MessageLog({ messages }: { messages: TimelineMessage[] }) {
  return (
    <div style={{ padding: 0 }}>
      {messages.map((msg, i) => (
        <div
          key={msg.message_id || i}
          style={{
            display: 'flex',
            padding: '8px 16px',
            borderBottom: '1px solid #F3F4F6',
            gap: 12,
            fontSize: 13,
          }}
        >
          <div style={{ minWidth: 50, fontFamily: 'monospace', color: '#6B7280', fontSize: 12 }}>
            {msg.sim_time}
          </div>
          <div style={{ minWidth: 90 }}>
            <span
              style={{
                fontWeight: 'bold',
                color: ROLE_COLORS[msg.sender] || '#333',
                fontSize: 12,
              }}
            >
              {msg.sender_name}
            </span>
          </div>
          <div style={{ flex: 1, lineHeight: 1.4 }}>
            {msg.related_event_id && (
              <span style={{ fontSize: 10, color: '#9CA3AF', marginRight: 4 }}>
                [#{msg.related_event_id}]
              </span>
            )}
            {msg.content.substring(0, 300)}{msg.content.length > 300 ? '...' : ''}
          </div>
          <div style={{ minWidth: 50, fontSize: 11, color: '#9CA3AF' }}>
            {msg.message_type}
          </div>
        </div>
      ))}
      {messages.length === 0 && (
        <div style={{ padding: 40, textAlign: 'center', color: '#9CA3AF' }}>
          メッセージがありません
        </div>
      )}
    </div>
  );
}

/* ─── State Summary (default right panel) ─── */

function StateSummary({ state }: { state: DisasterStateSummary }) {
  return (
    <div style={{ padding: 16, fontSize: 13 }}>
      <h3 style={{ fontSize: 14, margin: '0 0 12px' }}>現在の災害状況</h3>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 'bold', color: '#6B7280', marginBottom: 4 }}>警戒レベル</div>
        <div style={{ fontSize: 24, fontWeight: 'bold', color: state.alert_level >= 4 ? '#DC2626' : '#CA8A04' }}>
          レベル {state.alert_level}
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 'bold', color: '#6B7280', marginBottom: 4 }}>気象</div>
        <div>降水量: {state.weather.rainfall_mm_h} mm/h</div>
        {state.weather.alerts.length > 0 && (
          <div style={{ color: '#DC2626' }}>{state.weather.alerts.join(', ')}</div>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 'bold', color: '#6B7280', marginBottom: 4 }}>河川</div>
        {state.rivers.map((r, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <span>{r.name}</span>
            <span style={{ fontFamily: 'monospace', color: r.level_m >= r.danger_m ? '#DC2626' : '#333' }}>
              {r.level_m.toFixed(1)}m / {r.danger_m.toFixed(1)}m
            </span>
          </div>
        ))}
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 'bold', color: '#6B7280', marginBottom: 4 }}>状況</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
          <Stat label="対応中" value={state.active_incidents} />
          <Stat label="避難指示" value={state.evacuation_orders} />
          <Stat label="避難所" value={state.shelters_open} />
          <Stat label="負傷者" value={state.casualties.injured} />
          <Stat label="行方不明" value={state.casualties.missing} />
          <Stat label="避難済" value={state.casualties.evacuated} />
        </div>
      </div>

      <div>
        <div style={{ fontSize: 11, fontWeight: 'bold', color: '#6B7280', marginBottom: 4 }}>リソース</div>
        <div>救助チーム: {state.resources.rescue_teams}</div>
        <div>救急車: {state.resources.ambulances}</div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 6px', background: '#F9FAFB', borderRadius: 4 }}>
      <span style={{ fontSize: 12 }}>{label}</span>
      <span style={{ fontWeight: 'bold', fontFamily: 'monospace' }}>{value}</span>
    </div>
  );
}
