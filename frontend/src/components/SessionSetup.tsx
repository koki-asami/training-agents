import { useEffect, useRef, useState } from 'react';
import type { AgentRole, DifficultyLevel, RoleAssignment, SessionInfo } from '../types/simulation';
import { ROLE_DISPLAY_NAMES } from '../types/simulation';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

const ASSIGNABLE_ROLES: AgentRole[] = ['commander', 'soumu', 'shoubou', 'kensetsu', 'fukushi'];

const DIFFICULTY_OPTIONS: { value: DifficultyLevel; label: string; desc: string }[] = [
  { value: 'beginner', label: '初級（体制構築）', desc: 'ヒント付き、ゆっくりペース' },
  { value: 'intermediate', label: '中級（指揮判断）', desc: '標準ペース、リソース制約あり' },
  { value: 'advanced', label: '上級（指揮判断・上級）', desc: '高速、情報断片的、リソース不足' },
];

interface CachedScenario {
  filename: string;
  size_kb: number;
  modified: number;
}

type ScenarioSource = 'upload' | 'cached';

interface Props {
  onSessionCreated: (info: SessionInfo, participantId: string) => void;
}

export function SessionSetup({ onSessionCreated }: Props) {
  const [municipality, setMunicipality] = useState('熊本市');
  const [difficulty, setDifficulty] = useState<DifficultyLevel>('intermediate');
  const [scenarioSource, setScenarioSource] = useState<ScenarioSource>('cached');
  const [scenarioFile, setScenarioFile] = useState<File | null>(null);
  const [cachedScenarios, setCachedScenarios] = useState<CachedScenario[]>([]);
  const [selectedCached, setSelectedCached] = useState<string>('');
  const [assignments, setAssignments] = useState<RoleAssignment[]>(
    ASSIGNABLE_ROLES.map((role) => ({
      role,
      is_human: role === 'commander',
      participant_name: role === 'commander' ? '訓練者' : undefined,
    }))
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch cached scenarios on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/scenarios`)
      .then((res) => res.json())
      .then((data) => {
        const list: CachedScenario[] = data.scenarios || [];
        setCachedScenarios(list);
        // Auto-select most recent (first in list, sorted by modified desc)
        if (list.length > 0) {
          setSelectedCached(list[0].filename);
          setScenarioSource('cached');
        } else {
          setScenarioSource('upload');
        }
      })
      .catch(() => setScenarioSource('upload'));
  }, []);

  const toggleHuman = (index: number) => {
    setAssignments((prev) =>
      prev.map((a, i) =>
        i === index
          ? { ...a, is_human: !a.is_human, participant_name: !a.is_human ? '参加者' : undefined }
          : a
      )
    );
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    if (file) {
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (ext !== 'json' && ext !== 'xlsx') {
        setError('JSON または Excel (.xlsx) ファイルを選択してください');
        setScenarioFile(null);
        return;
      }
      setError('');
    }
    setScenarioFile(file);
  };

  const handleCreate = async () => {
    if (scenarioSource === 'upload' && !scenarioFile) {
      setError('シナリオファイルを選択してください');
      return;
    }
    if (scenarioSource === 'cached' && !selectedCached) {
      setError('シナリオを選択してください');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const formData = new FormData();
      if (scenarioSource === 'upload' && scenarioFile) {
        formData.append('scenario_file', scenarioFile);
      } else {
        formData.append('cached_scenario', selectedCached);
      }
      formData.append('difficulty', difficulty);
      formData.append('municipality', municipality);
      formData.append('role_assignments', JSON.stringify(assignments));

      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to create session');
      }
      const info: SessionInfo = await res.json();

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

  const canCreate =
    scenarioSource === 'cached' ? !!selectedCached : !!scenarioFile;

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

      {/* Scenario source toggle */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 'bold', marginBottom: 8 }}>シナリオ</label>

        {/* Source tabs */}
        <div style={{ display: 'flex', gap: 0, marginBottom: 8 }}>
          <button
            onClick={() => setScenarioSource('cached')}
            style={{
              flex: 1,
              padding: '8px 0',
              border: '1px solid #D1D5DB',
              borderRadius: '6px 0 0 6px',
              background: scenarioSource === 'cached' ? '#2563EB' : 'white',
              color: scenarioSource === 'cached' ? 'white' : '#333',
              cursor: 'pointer',
              fontWeight: scenarioSource === 'cached' ? 'bold' : 'normal',
              fontSize: 13,
            }}
          >
            保存済みシナリオ {cachedScenarios.length > 0 && `(${cachedScenarios.length})`}
          </button>
          <button
            onClick={() => setScenarioSource('upload')}
            style={{
              flex: 1,
              padding: '8px 0',
              border: '1px solid #D1D5DB',
              borderLeft: 'none',
              borderRadius: '0 6px 6px 0',
              background: scenarioSource === 'upload' ? '#2563EB' : 'white',
              color: scenarioSource === 'upload' ? 'white' : '#333',
              cursor: 'pointer',
              fontWeight: scenarioSource === 'upload' ? 'bold' : 'normal',
              fontSize: 13,
            }}
          >
            新規アップロード
          </button>
        </div>

        {scenarioSource === 'cached' ? (
          /* Cached scenario list */
          <div style={{ border: '1px solid #D1D5DB', borderRadius: 8, overflow: 'hidden' }}>
            {cachedScenarios.length === 0 ? (
              <div style={{ padding: 20, textAlign: 'center', color: '#9CA3AF', fontSize: 13 }}>
                保存済みシナリオがありません。新規アップロードしてください。
              </div>
            ) : (
              cachedScenarios.map((s) => (
                <label
                  key={s.filename}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '10px 12px',
                    borderBottom: '1px solid #F3F4F6',
                    cursor: 'pointer',
                    background: selectedCached === s.filename ? '#EFF6FF' : 'white',
                    transition: 'background 0.1s',
                  }}
                >
                  <input
                    type="radio"
                    name="cached_scenario"
                    checked={selectedCached === s.filename}
                    onChange={() => setSelectedCached(s.filename)}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: selectedCached === s.filename ? 'bold' : 'normal', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {s.filename}
                    </div>
                    <div style={{ fontSize: 11, color: '#9CA3AF' }}>
                      {s.size_kb} KB
                    </div>
                  </div>
                  {s === cachedScenarios[0] && (
                    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 8, background: '#DBEAFE', color: '#1E40AF' }}>
                      最新
                    </span>
                  )}
                </label>
              ))
            )}
          </div>
        ) : (
          /* File upload */
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              const file = e.dataTransfer.files?.[0];
              if (file) {
                const ext = file.name.split('.').pop()?.toLowerCase();
                if (ext === 'json' || ext === 'xlsx') {
                  setScenarioFile(file);
                  setError('');
                } else {
                  setError('JSON または Excel (.xlsx) ファイルを選択してください');
                }
              }
            }}
            style={{
              border: `2px dashed ${scenarioFile ? '#2563EB' : '#D1D5DB'}`,
              borderRadius: 8,
              padding: '24px 16px',
              textAlign: 'center',
              cursor: 'pointer',
              background: scenarioFile ? '#EFF6FF' : '#F9FAFB',
            }}
          >
            {scenarioFile ? (
              <div>
                <div style={{ fontSize: 14, fontWeight: 'bold', color: '#2563EB' }}>
                  {scenarioFile.name}
                </div>
                <div style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>
                  {(scenarioFile.size / 1024).toFixed(1)} KB
                </div>
                <div
                  style={{ fontSize: 12, color: '#DC2626', marginTop: 4, cursor: 'pointer' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setScenarioFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = '';
                  }}
                >
                  ファイルを変更
                </div>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 28, marginBottom: 4 }}>+</div>
                <div style={{ fontSize: 14, color: '#6B7280' }}>
                  クリックまたはドラッグ&ドロップでファイルを選択
                </div>
                <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>
                  JSON / Excel (.xlsx) 対応 — アップロード後に保存されます
                </div>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.xlsx"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
          </div>
        )}
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
        disabled={loading || !canCreate}
        style={{
          width: '100%',
          padding: 12,
          background: loading || !canCreate ? '#9CA3AF' : '#DC2626',
          color: 'white',
          border: 'none',
          borderRadius: 6,
          fontSize: 16,
          fontWeight: 'bold',
          cursor: loading || !canCreate ? 'not-allowed' : 'pointer',
        }}
      >
        {loading ? '作成中...' : '訓練セッションを作成'}
      </button>
    </div>
  );
}
