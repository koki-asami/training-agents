import { useEffect, useState } from 'react';
import { AdminDashboard } from './components/AdminDashboard';
import { Dashboard } from './components/Dashboard';
import { SessionSetup } from './components/SessionSetup';
import type { SessionInfo } from './types/simulation';

function App() {
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [participantId, setParticipantId] = useState<string | null>(null);

  // Check URL for admin mode: /admin/{sessionId}
  const path = window.location.pathname;
  const adminMatch = path.match(/^\/admin\/(.+)$/);

  if (adminMatch) {
    return <AdminDashboard sessionId={adminMatch[1]} />;
  }

  // Check URL for join mode: /join/{sessionId}/{participantId}
  const joinMatch = path.match(/^\/join\/(.+?)\/(.+)$/);

  if (joinMatch && !sessionInfo) {
    return (
      <Dashboard
        sessionInfo={{ session_id: joinMatch[1], participants: [], ai_roles: [], human_roles: [] }}
        participantId={joinMatch[2]}
      />
    );
  }

  if (!sessionInfo || !participantId) {
    return (
      <SessionSetup
        onSessionCreated={(info, pid) => {
          setSessionInfo(info);
          setParticipantId(pid);
          // Update URL so admin can be opened in another tab
          window.history.pushState({}, '', `/join/${info.session_id}/${pid}`);
        }}
      />
    );
  }

  return <Dashboard sessionInfo={sessionInfo} participantId={participantId} />;
}

export default App;
