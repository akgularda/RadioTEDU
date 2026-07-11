import { useEffect, useState } from 'react';

import { Dashboard } from './components/Dashboard';
import { PublicDashboard } from './components/PublicDashboard';
import { fetchPublicStatus, fetchStatus, type PublicStatusResponse, type StatusResponse } from './api';

function App() {
  const isPublicRoute = window.location.pathname === '/ai';
  if (isPublicRoute) {
    return <PublicApp />;
  }
  return <OperatorApp />;
}

function OperatorApp() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const payload = await fetchStatus();
      setStatus(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backend unavailable');
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, []);

  if (error && !status) {
    return (
      <main className="app-shell">
        <section className="station-card station-card--narrow">
          <div className="station-title-block">
            <h1>RadioTEDU</h1>
            <p>Backend unavailable</p>
          </div>
          <div className="empty-panel">{error}</div>
        </section>
      </main>
    );
  }

  if (!status) {
    return (
      <main className="app-shell">
        <section className="station-card station-card--narrow">
          <div className="station-title-block">
            <h1>RadioTEDU</h1>
            <p>Loading local station state</p>
          </div>
        </section>
      </main>
    );
  }

  return <Dashboard status={status} onRefresh={() => void refresh()} />;
}

function PublicApp() {
  const [status, setStatus] = useState<PublicStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const payload = await fetchPublicStatus();
      setStatus(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Public dashboard unavailable');
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, []);

  if (error && !status) {
    return (
      <main className="app-shell">
        <section className="station-card station-card--narrow">
          <div className="station-title-block">
            <h1>RadioTEDU</h1>
            <p>Public dashboard unavailable</p>
          </div>
          <div className="empty-panel">{error}</div>
        </section>
      </main>
    );
  }

  if (!status) {
    return (
      <main className="app-shell">
        <section className="station-card station-card--narrow">
          <div className="station-title-block">
            <h1>RadioTEDU</h1>
            <p>Loading public station state</p>
          </div>
        </section>
      </main>
    );
  }

  return <PublicDashboard status={status} connectionError={error} />;
}

export default App;
