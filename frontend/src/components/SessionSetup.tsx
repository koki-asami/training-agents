import { useState } from 'react';
import type { AgentRole, DifficultyLevel, RoleAssignment, SessionInfo } from '../types/simulation';
import { ROLE_DISPLAY_NAMES } from '../types/simulation';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const ASSIGNABLE_ROLES: AgentRole[] = ['commander', 'soumu', 'shoubou', 'kensetsu', 'fukushi'];

const DIFFICULTY_OPTIONS: { value: DifficultyLevel; label: string; desc: string }[] = [
  { value: 'beginner', label: '初級（体制構築）', desc: 'ヒント付き、ゆっくりペース' },
  { value: 'intermediate', label: '中級（指揮判断）', desc: '標準ペース、リソース制約あり' },
  { value: 'advanced', label: '上級（指揮判断・上級）', desc: '高速、情報断片的、リソース不足' },
];

interface Props {
  onSessionCreated: (info: SessionInfo, participantId: string) => void;
}

export function SessionSetup({ onSessionCreated }: Props) {
  const [municipality, setMunicipality] = useState('熊本市');
  const [difficulty, setDifficulty] = useState<DifficultyLevel>('intermediate');
  const [scenarioPath, setScenarioPath] = useState('data/scenarios/sample.json');
  const [assignments, setAssignments] = useState<RoleAssignment[]>(
    ASSIGNABLE_ROLES.map((role) => ({
      role,
      is_human: role === 'commander',
      participant_name: role === 'commander' ? '訓練者' : undefined,
    }))
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const toggleHuman = (index: number) => {
    setAssignments((prev) =>
      prev.map((a, i) =>
        i === index
          ? { ...a, is_human: !a.is_human, participant_name: !a.is_human ? '参加者' : undefined }
          : a
      )
    );
  };

  const handleCreate = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_path: scenarioPath,
          difficulty,
          municipality,
          role_assignments: assignments,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to create session');
      }
      const info: SessionInfo = await res.json();

      // Get the first human participant ID
      const firstParticipant = info.participants[0];
      if (firstParticipant) {
        onSessionCreated(info, firstParticipant.id);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 700, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>防災訓練シミュレーション</h1>
      <p style={{ color: '#666', marginBottom: 24 }}>セッション設定</p>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 'bold', marginBottom: 4 }}>自治体名</label>
        <input
          value={municipality}
          onChange={(e) => setMunicipality(e.target.value)}
          style={{ width: '100%', padding: 8, border: '1px solid #ccc', borderRadius: 4 }}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 'bold', marginBottom: 4 }}>シナリオファイル</label>
        <input
          value={scenarioPath}
          onChange={(e) => setScenarioPath(e.target.value)}
          style={{ width: '100%', padding: 8, border: '1px solid #ccc', borderRadius: 4 }}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 'bold', marginBottom: 8 }}>難易度</label>
        {DIFFICULTY_OPTIONS.map((opt) => (
          <label
            key={opt.value}
            style={{
              display: 'block',
              padding: '8px 12px',
              marginBottom: 4,
              border: `2px solid ${difficulty === opt.value ? '#2563EB' : '#e5e7eb'}`,
              borderRadius: 6,
              cursor: 'pointer',
              background: difficulty === opt.value ? '#eff6ff' : 'white',
            }}
          >
            <input
              type="radio"
              checked={difficulty === opt.value}
              onChange={() => setDifficulty(opt.value)}
              style={{ marginRight: 8 }}
            />
            <strong>{opt.label}</strong>
            <span style={{ color: '#666', marginLeft: 8 }}>{opt.desc}</span>
          </label>
        ))}
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 'bold', marginBottom: 8 }}>役割割当</label>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
              <th style={{ textAlign: 'left', padding: 8 }}>役割</th>
              <th style={{ textAlign: 'center', padding: 8 }}>担当</th>
              <th style={{ textAlign: 'left', padding: 8 }}>参加者名</th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((a, i) => (
              <tr key={a.role} style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: 8 }}>{ROLE_DISPLAY_NAMES[a.role]?.[0] || a.role}</td>
                <td style={{ textAlign: 'center', padding: 8 }}>
                  <button
                    onClick={() => toggleHuman(i)}
                    style={{
                      padding: '4px 12px',
                      borderRadius: 12,
                      border: 'none',
                      cursor: 'pointer',
                      background: a.is_human ? '#2563EB' : '#e5e7eb',
                      color: a.is_human ? 'white' : '#333',
                      fontSize: 13,
                    }}
                  >
                    {a.is_human ? '人間' : 'AI'}
                  </button>
                </td>
                <td style={{ padding: 8 }}>
                  {a.is_human && (
                    <input
                      value={a.participant_name || ''}
                      onChange={(e) =>
                        setAssignments((prev) =>
                          prev.map((x, j) =>
                            j === i ? { ...x, participant_name: e.target.value } : x
                          )
                        )
                      }
                      placeholder="参加者名"
                      style={{ padding: 4, border: '1px solid #ccc', borderRadius: 4, width: '100%' }}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error && (
        <div style={{ color: 'red', marginBottom: 16, padding: 8, background: '#fef2f2', borderRadius: 4 }}>
          {error}
        </div>
      )}

      <button
        onClick={handleCreate}
        disabled={loading}
        style={{
          width: '100%',
          padding: 12,
          background: loading ? '#9CA3AF' : '#DC2626',
          color: 'white',
          border: 'none',
          borderRadius: 6,
          fontSize: 16,
          fontWeight: 'bold',
          cursor: loading ? 'not-allowed' : 'pointer',
        }}
      >
        {loading ? '作成中...' : '訓練セッションを作成'}
      </button>
    </div>
  );
}
