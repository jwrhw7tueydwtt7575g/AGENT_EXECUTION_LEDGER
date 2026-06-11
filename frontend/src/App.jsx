import React from 'react';
import './index.css';
import { AppProvider, useApp } from './AppContext';
import DagExplorer from './views/DagExplorer';
import ReceiptInspector from './views/ReceiptInspector';
import DriftTimeline from './views/DriftTimeline';
import RunComparison from './views/RunComparison';
import AnomalyScorecard from './views/AnomalyScorecard';
import RunSelector from './components/RunSelector';
import LiveFeed from './components/LiveFeed';

const NAV = [
  { id: 'dag', icon: '🕸️', label: 'DAG Explorer' },
  { id: 'receipt', icon: '🧾', label: 'Receipt Inspector' },
  { id: 'drift', icon: '📈', label: 'Drift Timeline' },
  { id: 'compare', icon: '⚡', label: 'Run Comparison' },
  { id: 'anomaly', icon: '🚨', label: 'Anomaly Scorecard' },
];

function Dashboard() {
  const { view, setView, wsConnected, stats } = useApp();

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">Agent System</div>
          <h1>Execution Ledger</h1>
        </div>

        <div className="nav-section-label">Dashboard</div>
        {NAV.map(n => (
          <div
            key={n.id}
            className={`nav-item ${view === n.id ? 'active' : ''}`}
            onClick={() => setView(n.id)}
          >
            <span className="icon">{n.icon}</span>
            {n.label}
          </div>
        ))}

        <div className="sidebar-bottom">
          <div className="ws-status">
            <div className={`ws-dot ${wsConnected ? 'connected' : ''}`}></div>
            <span>{wsConnected ? 'Live Connected' : 'Reconnecting...'}</span>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="main-content">
        {/* Top bar */}
        <header className="topbar">
          <div>
            <div className="topbar-title">{NAV.find(n => n.id === view)?.label}</div>
            <div className="topbar-sub">Agent Execution Ledger — Real-time AI pipeline observability</div>
          </div>
          <div className="topbar-actions">
            {stats && (
              <>
                <div className="stat-pill">
                  <span>Runs</span><span className="val">{stats.total_runs}</span>
                </div>
                <div className="stat-pill">
                  <span>Receipts</span><span className="val">{stats.total_receipts}</span>
                </div>
                <div className="stat-pill" style={{ borderColor: stats.critical_nodes > 0 ? 'rgba(245,101,101,0.3)' : 'var(--border)' }}>
                  <span>🔴 Critical</span><span className="val" style={{ color: stats.critical_nodes > 0 ? 'var(--status-critical)' : 'inherit' }}>{stats.critical_nodes}</span>
                </div>
                <div className="stat-pill">
                  <span>Trust</span><span className="val" style={{ color: 'var(--status-verified)' }}>{stats.avg_trust_score != null ? (stats.avg_trust_score * 100).toFixed(1) + '%' : '—'}</span>
                </div>
              </>
            )}
          </div>
        </header>

        {/* Content area */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Left rail: Run selector + Live feed */}
          <aside style={{
            width: 260, flexShrink: 0, overflowY: 'auto',
            borderRight: '1px solid var(--border)',
            padding: 16,
            background: 'var(--bg-secondary)',
          }}>
            <RunSelector />
            <LiveFeed />
          </aside>

          {/* Main view */}
          <main className="page" style={{ flex: 1, overflowY: 'auto' }}>
            {view === 'dag' && <DagExplorer />}
            {view === 'receipt' && <ReceiptInspector />}
            {view === 'drift' && <DriftTimeline />}
            {view === 'compare' && <RunComparison />}
            {view === 'anomaly' && <AnomalyScorecard />}
          </main>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Dashboard />
    </AppProvider>
  );
}
