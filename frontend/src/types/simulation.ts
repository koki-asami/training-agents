// Core types for the disaster training simulation

export type DifficultyLevel = 'beginner' | 'intermediate' | 'advanced';

export type AgentRole =
  | 'scenario_master'
  | 'commander'
  | 'soumu'
  | 'shoubou'
  | 'kensetsu'
  | 'fukushi'
  | 'juumin'
  | 'kishou';

export type SimulationPhase = 'setup' | 'running' | 'paused' | 'completed';

export const ROLE_DISPLAY_NAMES: Record<AgentRole, [string, string]> = {
  scenario_master: ['シナリオマスター', 'Scenario Master'],
  commander: ['災害対策本部長', 'Commander'],
  soumu: ['総務部', 'General Affairs'],
  shoubou: ['消防局', 'Fire Department'],
  kensetsu: ['建設部', 'Construction'],
  fukushi: ['福祉部', 'Welfare'],
  juumin: ['住民', 'Resident'],
  kishou: ['気象情報', 'Weather'],
};

export const ROLE_COLORS: Record<string, string> = {
  scenario_master: '#6B7280',
  commander: '#DC2626',
  soumu: '#2563EB',
  shoubou: '#EA580C',
  kensetsu: '#65A30D',
  fukushi: '#9333EA',
  juumin: '#0891B2',
  kishou: '#0284C7',
};

export interface SimulationMessage {
  type: 'message';
  sender: string;
  sender_name: string;
  content: string;
  sim_time: string;
  message_type: string;
  related_event_id?: string;
  source?: string;                  // 情報源 (住民, 警察, etc.)
  responsible_department?: string;   // 対応部署 (総務部, 消防局, etc.)
}

export interface StateUpdate {
  type: 'state_update';
  state: DisasterStateSummary;
}

export interface SystemMessage {
  type: 'system';
  content: string;
}

export type WSMessage = SimulationMessage | StateUpdate | SystemMessage | { type: 'error'; content: string };

export interface DisasterStateSummary {
  sim_time: string;
  alert_level: number;
  weather: {
    rainfall_mm_h: number;
    alerts: string[];
  };
  rivers: {
    name: string;
    level_m: number;
    danger_m: number;
    trend: string;
  }[];
  active_incidents: number;
  evacuation_orders: number;
  shelters_open: number;
  resources: {
    rescue_teams: string;
    ambulances: string;
  };
  casualties: {
    injured: number;
    missing: number;
    evacuated: number;
  };
}

export interface Participant {
  id: string;
  name: string;
  role: AgentRole;
}

export interface SessionInfo {
  session_id: string;
  participants: Participant[];
  ai_roles: string[];
  human_roles: string[];
}

export interface RoleAssignment {
  role: AgentRole;
  is_human: boolean;
  participant_name?: string;
}
