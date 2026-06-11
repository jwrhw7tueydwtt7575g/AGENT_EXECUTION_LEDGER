import React from 'react';
import { useApp } from '../AppContext';

export default function RunSelector() {
    const {
        runs, selectedRunId, setSelectedRunId,
        liveRunId, autoSwitchToLatest, setAutoSwitchToLatest,
    } = useApp();

    return (
        <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
                <h3>Active Runs</h3>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{runs.length}</span>
            </div>

            {/* Auto-switch toggle */}
            <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 14px 8px', borderBottom: '1px solid var(--border)',
                fontSize: '0.72rem', color: 'var(--text-muted)',
            }}>
                <span>Auto-switch to latest</span>
                <button
                    onClick={() => setAutoSwitchToLatest(v => !v)}
                    style={{
                        background: autoSwitchToLatest ? 'var(--accent-blue)' : 'var(--bg-secondary)',
                        border: '1px solid var(--border)',
                        borderRadius: 12,
                        padding: '2px 10px',
                        fontSize: '0.68rem',
                        color: autoSwitchToLatest ? '#fff' : 'var(--text-muted)',
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        fontWeight: 600,
                    }}
                >
                    {autoSwitchToLatest ? 'ON' : 'OFF'}
                </button>
            </div>

            <div style={{ maxHeight: 280, overflowY: 'auto' }}>
                {runs.length === 0 && (
                    <div style={{ padding: '16px', color: 'var(--text-muted)', fontSize: '0.78rem', textAlign: 'center' }}>
                        No runs yet. Start an agent.
                    </div>
                )}
                {runs.map(r => {
                    const isSelected = selectedRunId === r.run_id;
                    const isLive = liveRunId === r.run_id;
                    return (
                        <div
                            key={r.run_id}
                            className={`run-item ${isSelected ? 'selected' : ''}`}
                            onClick={() => { setSelectedRunId(r.run_id); setAutoSwitchToLatest(false); }}
                        >
                            <span className={`node-dot ${r.chain_verified ? 'verified' : 'minor_issue'}`} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <div style={{ fontWeight: 600, fontSize: '0.78rem', fontFamily: 'JetBrains Mono' }}>
                                        {r.run_id.slice(0, 12)}...
                                    </div>
                                    {isLive && (
                                        <span style={{
                                            fontSize: '0.58rem', fontWeight: 700,
                                            background: 'rgba(72,187,120,0.15)',
                                            color: 'var(--status-verified)',
                                            border: '1px solid rgba(72,187,120,0.3)',
                                            borderRadius: 4, padding: '1px 5px',
                                            animation: 'pulse 1.5s infinite',
                                        }}>
                                            ● LIVE
                                        </span>
                                    )}
                                </div>
                                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                                    {r.agent_name} • {r.framework} • {r.total_receipts ?? r.total_steps} receipts
                                </div>
                            </div>
                            <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                <div style={{
                                    fontSize: '0.72rem', fontWeight: 700,
                                    color: r.avg_drift > 0.35 ? 'var(--status-critical)' : 'var(--status-verified)'
                                }}>
                                    {r.avg_drift?.toFixed(3) ?? '—'}
                                </div>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>drift</div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
