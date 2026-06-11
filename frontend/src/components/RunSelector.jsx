import React from 'react';
import { useApp } from '../AppContext';

export default function RunSelector() {
    const { runs, selectedRunId, setSelectedRunId } = useApp();

    return (
        <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header"><h3>Active Runs</h3></div>
            <div style={{ maxHeight: 280, overflowY: 'auto' }}>
                {runs.map(r => (
                    <div
                        key={r.run_id}
                        className={`run-item ${selectedRunId === r.run_id ? 'selected' : ''}`}
                        onClick={() => setSelectedRunId(r.run_id)}
                    >
                        <span className={`node-dot ${r.chain_verified ? 'verified' : 'minor_issue'}`}></span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontWeight: 600, fontSize: '0.78rem', fontFamily: 'JetBrains Mono' }}>
                                {r.run_id.slice(0, 12)}...
                            </div>
                            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                                {r.agent_name} • {r.framework} • {r.total_steps} steps
                            </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: r.avg_drift > 0.35 ? 'var(--status-critical)' : 'var(--status-verified)' }}>
                                {r.avg_drift?.toFixed(3)}
                            </div>
                            <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>drift</div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
