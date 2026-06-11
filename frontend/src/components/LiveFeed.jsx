import React, { useState } from 'react';
import { useApp } from '../AppContext';

const STATUS_COLOR = {
    verified: '#48bb78', minor_issue: '#ecc94b',
    significant_issue: '#ed8936', critical: '#f56565',
    ghost: '#666', pending: '#4a5568',
};

export default function LiveFeedSidebar() {
    const { liveReceiptsByRun, liveRunId, wsConnected, setSelectedRunId, setAutoSwitchToLatest } = useApp();
    const [collapsed, setCollapsed] = useState({});

    // Build an ordered list of run IDs (newest first — liveRunId first)
    const runIds = Object.keys(liveReceiptsByRun).sort((a, b) => {
        if (a === liveRunId) return -1;
        if (b === liveRunId) return 1;
        return 0;
    });

    const totalEvents = Object.values(liveReceiptsByRun).reduce((s, arr) => s + arr.length, 0);

    const toggleCollapse = (rid) =>
        setCollapsed(prev => ({ ...prev, [rid]: !prev[rid] }));

    const jumpToRun = (rid) => {
        setAutoSwitchToLatest(false);
        setSelectedRunId(rid);
    };

    return (
        <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className={`ws-dot ${wsConnected ? 'connected' : ''}`} />
                    <h3>{wsConnected ? 'Live Feed' : 'Feed Offline'}</h3>
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{totalEvents} events</span>
            </div>

            <div className="live-feed" style={{ padding: '0 8px', maxHeight: 420, overflowY: 'auto' }}>
                {runIds.length === 0 && (
                    <div style={{ padding: '20px 8px', color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.8rem' }}>
                        Waiting for live events…
                    </div>
                )}

                {runIds.map(rid => {
                    const receipts = liveReceiptsByRun[rid] || [];
                    const isLive = rid === liveRunId;
                    const isOpen = !collapsed[rid];

                    return (
                        <div key={rid} style={{ marginBottom: 8 }}>
                            {/* Run heading */}
                            <div
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 6,
                                    padding: '5px 8px', borderRadius: 6, cursor: 'pointer',
                                    background: isLive ? 'rgba(72,187,120,0.07)' : 'var(--bg-secondary)',
                                    border: isLive ? '1px solid rgba(72,187,120,0.25)' : '1px solid var(--border)',
                                    marginBottom: 4,
                                }}
                                onClick={() => toggleCollapse(rid)}
                            >
                                {isLive && (
                                    <span style={{
                                        width: 7, height: 7, borderRadius: '50%',
                                        background: 'var(--status-verified)',
                                        flexShrink: 0,
                                        animation: 'pulse 1.5s infinite',
                                    }} />
                                )}
                                <span style={{
                                    fontFamily: 'JetBrains Mono', fontSize: '0.68rem',
                                    color: isLive ? 'var(--status-verified)' : 'var(--text-muted)',
                                    flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                }}>
                                    {rid.slice(0, 12)}…
                                </span>
                                <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                                    {receipts.length} {isOpen ? '▾' : '▸'}
                                </span>
                                <button
                                    title="Jump to run"
                                    onClick={(e) => { e.stopPropagation(); jumpToRun(rid); }}
                                    style={{
                                        background: 'none', border: 'none', cursor: 'pointer',
                                        color: 'var(--accent-blue)', fontSize: '0.68rem', padding: '0 2px',
                                    }}
                                >
                                    ↗
                                </button>
                            </div>

                            {/* Receipts under this run */}
                            {isOpen && [...receipts].reverse().slice(0, 12).map((r, i) => (
                                <div key={r.receipt_id + i} className="live-feed-item" style={{ paddingLeft: 16 }}>
                                    <span className={`node-dot ${r.node_status}`} style={{ marginTop: 2, flexShrink: 0 }} />
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ fontWeight: 600, fontSize: '0.76rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                            {r.tool_name} <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>via {r.agent_id}</span>
                                        </div>
                                        {r.drift_score != null && (
                                            <div style={{ fontSize: '0.66rem', color: STATUS_COLOR[r.node_status] || 'var(--text-muted)' }}>
                                                drift {r.drift_score.toFixed(3)} • {r.latency_ms?.toFixed(0)}ms
                                            </div>
                                        )}
                                        {r.anomaly_flags?.length > 0 && (
                                            <div style={{ color: 'var(--status-critical)', fontSize: '0.65rem' }}>
                                                ⚠ {r.anomaly_flags.join(', ')}
                                            </div>
                                        )}
                                    </div>
                                    <span className="ts">
                                        {r.timestamp ? new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
                                    </span>
                                </div>
                            ))}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
