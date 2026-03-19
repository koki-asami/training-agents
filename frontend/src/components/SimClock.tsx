/**
 * Unified simulation clock display used across all screens.
 *
 * Variants:
 * - "header": compact inline display for navigation bars (Dashboard, Admin)
 * - "panel": larger display with label for status panels
 * - "inline": smallest, for message timestamps etc.
 */

interface SimClockProps {
  time: string;
  variant?: 'header' | 'panel' | 'inline';
  paused?: boolean;
  label?: boolean; // show "訓練時刻" label (default: true for header/panel)
}

const STYLES = {
  header: {
    wrapper: {
      display: 'inline-flex' as const,
      alignItems: 'center' as const,
      gap: 6,
      padding: '3px 10px',
      background: '#111827',
      borderRadius: 6,
      border: '1px solid #374151',
    },
    label: { fontSize: 10, color: '#9CA3AF', letterSpacing: 1 },
    time: { fontSize: 20, fontWeight: 'bold' as const, fontFamily: 'monospace', color: '#F9FAFB' },
  },
  panel: {
    wrapper: {
      display: 'flex' as const,
      flexDirection: 'column' as const,
      alignItems: 'flex-start' as const,
      gap: 2,
    },
    label: { fontSize: 11, color: '#6B7280', letterSpacing: 1 },
    time: { fontSize: 28, fontWeight: 'bold' as const, fontFamily: 'monospace', color: '#111827' },
  },
  inline: {
    wrapper: { display: 'inline-flex' as const, alignItems: 'center' as const },
    label: { display: 'none' as const },
    time: { fontSize: 12, fontFamily: 'monospace', color: '#6B7280' },
  },
};

export function SimClock({ time, variant = 'header', paused, label }: SimClockProps) {
  const showLabel = label ?? (variant !== 'inline');
  const s = STYLES[variant];

  return (
    <div style={s.wrapper}>
      {showLabel && <span style={s.label}>訓練時刻</span>}
      <span style={{
        ...s.time,
        ...(paused ? { animation: 'blink 1s step-end infinite' } : {}),
      }}>
        {time || '--:--'}
      </span>
      {paused && (
        <span style={{
          fontSize: 10,
          padding: '1px 6px',
          borderRadius: 6,
          background: '#CA8A04',
          color: 'white',
          marginLeft: 4,
        }}>
          停止中
        </span>
      )}
      <style>{`@keyframes blink { 50% { opacity: 0.5; } }`}</style>
    </div>
  );
}
