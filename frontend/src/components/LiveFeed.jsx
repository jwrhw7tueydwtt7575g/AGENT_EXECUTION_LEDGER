import React, { useState, useEffect } from 'react';
import { useApp } from '../AppContext';

const STATUS_COLOR = {
    verified: '#48bb78', minor_issue: '#ecc94b',
    significant_issue: '#ed8936', critical: '#f56565',
    ghost: '#666', pending: '#4a5568',
};

export default function LiveFeedSidebar() {
    const { liveReceipts, wsConnected } = useApp();
    const recent = liveReceipts.slice(0, 20);

    return (
        <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className={`ws-dot ${wsConnected ? 'connected' : ''}`}></div>
                    <h3>{wsConnected ? 'Live Feed' : 'Feed Offline'}</h3>
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{liveReceipts.length} events</span>
            </div>
            <div className="live-feed" style={{ padding: '0 16px' }}>
                {recent.length === 0 && (
                    <div style={{ padding: '20px 0', color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.8rem' }}>
                        Waiting for live events...
                    </div>
                )}
                {recent.map((r, i) => (
                    <div key={r.receipt_id + i} className="live-feed-item">
                        <span className={`node-dot ${r.node_status}`} style={{ marginTop: 2, flexShrink: 0 }}></span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontWeight: 600, fontSize: '0.78rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {r.tool_name} <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>via {r.agent_id}</span>
                            </div>
                            {r.drift_score != null && (
                                <div style={{ fontSize: '0.68rem', color: STATUS_COLOR[r.node_status] || 'var(--text-muted)' }}>
                                    drift {r.drift_score.toFixed(3)} • {r.latency_ms?.toFixed(0)}ms
                                </div>
                            )}
                            {r.anomaly_flags?.length > 0 && (
                                <div style={{ color: 'var(--status-critical)', fontSize: '0.68rem' }}>
                                    ⚠ {r.anomaly_flags.join(', ')}
                                </div>
                            )}
                        </div>
                        <span className="ts">{r.timestamp ? new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
