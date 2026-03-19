import { useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { SessionSetup } from './components/SessionSetup';
import type { SessionInfo } from './types/simulation';

function App() {
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [participantId, setParticipantId] = useState<string | null>(null);

  if (!sessionInfo || !participantId) {
    return (
      <SessionSetup
        onSessionCreated={(info, pid) => {
          setSessionInfo(info);
          setParticipantId(pid);
        }}
      />
    );
  }

  return <Dashboard sessionInfo={sessionInfo} participantId={participantId} />;
}

export default App;
