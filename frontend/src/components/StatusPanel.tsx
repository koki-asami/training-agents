import type { DisasterStateSummary } from '../types/simulation';

const ALERT_LEVEL_LABELS: Record<number, { label: string; color: string; bg: string }> = {
  1: { label: 'レベル1 早期注意', color: '#6B7280', bg: '#F3F4F6' },
  2: { label: 'レベル2 注意報', color: '#CA8A04', bg: '#FEF9C3' },
  3: { label: 'レベル3 高齢者等避難', color: '#EA580C', bg: '#FFF7ED' },
  4: { label: 'レベル4 避難指示', color: '#DC2626', bg: '#FEF2F2' },
  5: { label: 'レベル5 緊急安全確保', color: '#7C2D12', bg: '#431407' },
};

interface Props {
  state: DisasterStateSummary | null;
  simTime: string;
}

export function StatusPanel({ state, simTime }: Props) {
  if (!state) {
    return (
      <div style={{ padding: 16, color: '#999', textAlign: 'center' }}>
        訓練開始を待機中...
      </div>
    );
  }

  const alert = ALERT_LEVEL_LABELS[state.alert_level] || ALERT_LEVEL_LABELS[1];

  return (
    <div style={{ padding: 12, fontSize: 13, display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Time and Alert Level */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 11, color: '#999' }}>訓練時刻</div>
          <div style={{ fontSize: 24, fontWeight: 'bold', fontFamily: 'monospace' }}>
            {simTime || state.sim_time}
          </div>
        </div>
        <div
          style={{
            padding: '6px 12px',
            borderRadius: 6,
            background: alert.bg,
            color: alert.color,
            fontWeight: 'bold',
            fontSize: 12,
          }}
        >
          {alert.label}
        </div>
      </div>

      {/* Weather */}
      <Section title="気象情報">
        <div>降水量: {state.weather.rainfall_mm_h} mm/h</div>
        {state.weather.alerts.length > 0 && (
          <div style={{ color: '#DC2626' }}>
            発令中: {state.weather.alerts.join(', ')}
          </div>
        )}
      </Section>

      {/* Rivers */}
      <Section title="河川水位">
        {state.rivers.map((r, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>{r.name}</span>
            <span style={{ color: r.level_m >= r.danger_m ? '#DC2626' : '#333', fontFamily: 'monospace' }}>
              {r.level_m.toFixed(1)}m / {r.danger_m.toFixed(1)}m {r.trend === 'rising' ? '↑' : r.trend === 'falling' ? '↓' : '→'}
            </span>
          </div>
        ))}
      </Section>

      {/* Resources */}
      <Section title="リソース">
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>救助チーム</span>
          <span style={{ fontFamily: 'monospace' }}>{state.resources.rescue_teams}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>救急車</span>
          <span style={{ fontFamily: 'monospace' }}>{state.resources.ambulances}</span>
        </div>
      </Section>

      {/* Status Counts */}
      <Section title="状況">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
          <StatBadge label="対応中" value={state.active_incidents} color="#EA580C" />
          <StatBadge label="避難指示" value={state.evacuation_orders} color="#DC2626" />
          <StatBadge label="避難所" value={state.shelters_open} color="#2563EB" />
          <StatBadge label="負傷者" value={state.casualties.injured} color="#7C2D12" />
          <StatBadge label="行方不明" value={state.casualties.missing} color="#7C2D12" />
          <StatBadge label="避難済" value={state.casualties.evacuated} color="#15803D" />
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          fontWeight: 'bold',
          color: '#6B7280',
          textTransform: 'uppercase',
          marginBottom: 4,
          borderBottom: '1px solid #E5E7EB',
          paddingBottom: 2,
        }}
      >
        {title}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>{children}</div>
    </div>
  );
}

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '4px 8px',
        background: '#F9FAFB',
        borderRadius: 4,
      }}
    >
      <span style={{ fontSize: 12 }}>{label}</span>
      <span style={{ fontWeight: 'bold', color, fontFamily: 'monospace' }}>{value}</span>
    </div>
  );
}
