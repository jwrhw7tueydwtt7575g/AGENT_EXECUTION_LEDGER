import React, { useState, useEffect } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, Cell, PieChart, Pie, Legend
} from 'recharts';
import { useApp } from '../AppContext';
import { apiFetch } from '../api';

const FAILURE_LABELS = {
    F1: 'Silent API Failure',
    F2: 'Timeout Hallucination',
    F3: 'Ghost Tool Call',
    F4: 'Stale Cache Drift',
    F5: 'Multi-Agent Semantic Drift',
    F6: 'Confidence Inflation',
    F7: 'Tampered Replay',
    F8: 'Permission Boundary Violation'
};

const PALETTE = ['#63b3ed', '#9f7aea', '#68d391', '#ecc94b', '#ed8936', '#f56565', '#4fd1c5', '#fc8181'];

const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    return (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', fontSize: '0.78rem' }}>
            <div style={{ fontWeight: 700 }}>{payload[0]?.name}</div>
            <div style={{ color: 'var(--text-muted)' }}>Count: <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{payload[0]?.value}</span></div>
        </div>
    );
};

export default function AnomalyScorecard() {
    const { stats, runs, liveReceipts } = useApp();
    const [anomalies, setAnomalies] = useState([]);

    useEffect(() => {
        apiFetch('/anomalies?limit=40')
            .then(d => setAnomalies(d.anomalies || []))
            .catch(() => { });
    }, []);

    const failureDist = (stats?.failure_distribution || []).map((f, i) => ({
        name: FAILURE_LABELS[f._id] || f._id,
        shortName: f._id,
        count: f.count,
        fill: PALETTE[i % PALETTE.length]
    }));

    // Build cross-run heatmap: run x failure_type
    const heatmapRuns = runs.slice(0, 6);
    const failureKeys = Object.keys(FAILURE_LABELS);

    // latency distribution from live receipts
    const latencyBuckets = [
        { range: '<200ms', count: 0 },
        { range: '200-500ms', count: 0 },
        { range: '500-1000ms', count: 0 },
        { range: '1-2s', count: 0 },
        { range: '>2s', count: 0 },
    ];
    liveReceipts.forEach(r => {
        const l = r.latency_ms;
        if (!l) return;
        if (l < 200) latencyBuckets[0].count++;
        else if (l < 500) latencyBuckets[1].count++;
        else if (l < 1000) latencyBuckets[2].count++;
        else if (l < 2000) latencyBuckets[3].count++;
        else latencyBuckets[4].count++;
    });

    return (
        <div className="fade-in">
            <div style={{ marginBottom: 16 }}>
                <h2 style={{ marginBottom: 4 }}>Anomaly Scorecard</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    Cross-run anomaly statistics, failure mode distribution, and latency outliers
                </p>
            </div>

            {/* Top stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
                {[
                    { label: 'Total Runs', value: stats?.total_runs ?? '—', color: 'var(--accent-blue)' },
                    { label: 'Ghost Calls', value: stats?.ghost_calls ?? '—', color: '#666' },
                    { label: 'Critical Nodes', value: stats?.critical_nodes ?? '—', color: 'var(--status-critical)' },
                    { label: 'Avg Trust Score', value: stats?.avg_trust_score != null ? (stats.avg_trust_score * 100).toFixed(1) + '%' : '—', color: 'var(--status-verified)' },
                ].map(({ label, value, color }) => (
                    <div key={label} className="metric-card" style={{ borderTop: `3px solid ${color}` }}>
                        <div className="label">{label}</div>
                        <div className="value" style={{ color }}>{value}</div>
                    </div>
                ))}
            </div>

            <div className="grid-2" style={{ marginBottom: 20 }}>
                {/* Failure distribution bar chart */}
                <div className="card">
                    <div className="card-header"><h3>Failure Mode Distribution (F1–F8)</h3></div>
                    <div className="card-body" style={{ padding: '16px 0' }}>
                        {failureDist.length > 0 ? (
                            <ResponsiveContainer width="100%" height={240}>
                                <BarChart data={failureDist} margin={{ top: 5, right: 20, left: 0, bottom: 60 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                    <XAxis dataKey="shortName" stroke="var(--text-muted)" tick={{ fontSize: 11 }} />
                                    <YAxis stroke="var(--text-muted)" tick={{ fontSize: 11 }} />
                                    <Tooltip content={<CustomTooltip />} />
                                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                                        {failureDist.map((entry, i) => (
                                            <Cell key={i} fill={entry.fill} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                                No failure data available
                            </div>
                        )}
                        <div style={{ padding: '0 20px', display: 'flex', flexWrap: 'wrap', gap: '6px 14px' }}>
                            {failureDist.map((f, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                                    <span style={{ width: 8, height: 8, borderRadius: 2, background: f.fill, display: 'inline-block' }}></span>
                                    <span style={{ color: f.fill, fontWeight: 700 }}>{f.shortName}</span> {FAILURE_LABELS[f.shortName]?.slice(0, 20)}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Latency distribution */}
                <div className="card">
                    <div className="card-header"><h3>Latency Distribution (Live Feed)</h3></div>
                    <div className="card-body" style={{ padding: '16px 0' }}>
                        <ResponsiveContainer width="100%" height={240}>
                            <BarChart data={latencyBuckets} margin={{ top: 5, right: 20, left: 0, bottom: 20 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                <XAxis dataKey="range" stroke="var(--text-muted)" tick={{ fontSize: 11 }} />
                                <YAxis stroke="var(--text-muted)" tick={{ fontSize: 11 }} />
                                <Tooltip />
                                <Bar dataKey="count" fill="var(--accent-purple)" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Anomalous receipts table */}
            <div className="card">
                <div className="card-header">
                    <h3>Recent Anomalous Receipts</h3>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{anomalies.length} entries</span>
                </div>
                <div className="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Status</th>
                                <th>Tool</th>
                                <th>Agent</th>
                                <th>Drift</th>
                                <th>Anomaly Flags</th>
                                <th>Failure Types</th>
                                <th>Latency</th>
                            </tr>
                        </thead>
                        <tbody>
                            {anomalies.slice(0, 15).map(a => (
                                <tr key={a.receipt_id}>
                                    <td><span className={`node-dot ${a.node_status}`} style={{ display: 'inline-block' }}></span></td>
                                    <td style={{ fontWeight: 600 }}>{a.tool_name}</td>
                                    <td style={{ color: 'var(--text-muted)' }}>{a.agent_id}</td>
                                    <td style={{ fontWeight: 700, color: a.drift_score > 0.6 ? 'var(--status-critical)' : a.drift_score > 0.35 ? 'var(--status-significant)' : 'var(--status-minor)' }}>
                                        {a.drift_score?.toFixed(3) ?? '—'}
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                                            {a.anomaly_flags?.map(f => <span key={f} className="badge badge-critical" style={{ fontSize: '0.6rem' }}>{f}</span>)}
                                            {!a.anomaly_flags?.length && <span style={{ color: 'var(--text-muted)' }}>—</span>}
                                        </div>
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                                            {a.failure_types?.map(f => <span key={f} className={`tag tag-${f.toLowerCase()}`}>{f}</span>)}
                                            {!a.failure_types?.length && <span style={{ color: 'var(--text-muted)' }}>—</span>}
                                        </div>
                                    </td>
                                    <td className="mono">{a.latency_ms?.toFixed(0)}ms</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
