import React, { useState, useEffect, useCallback } from 'react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, ReferenceLine, Legend
} from 'recharts';
import { useApp } from '../AppContext';

const STATUS_COLORS = {
    verified: '#48bb78',
    minor_issue: '#ecc94b',
    significant_issue: '#ed8936',
    critical: '#f56565',
    ghost: '#666',
    pending: '#4a5568',
};

const CustomDot = (props) => {
    const { cx, cy, payload } = props;
    const color = STATUS_COLORS[payload.node_status] || '#4a5568';
    if (payload.node_status === 'critical') {
        return (
            <g>
                <circle cx={cx} cy={cy} r={7} fill={color} fillOpacity={0.2} />
                <circle cx={cx} cy={cy} r={4} fill={color} />
            </g>
        );
    }
    return <circle cx={cx} cy={cy} r={4} fill={color} stroke="var(--bg-card)" strokeWidth={2} />;
};

const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0]?.payload;
    return (
        <div style={{
            background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
            padding: '10px 14px', fontSize: '0.78rem'
        }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Step {d?.step_index}</div>
            <div style={{ color: 'var(--text-muted)' }}>Tool: <span style={{ color: 'var(--text-primary)' }}>{d?.tool_name}</span></div>
            <div style={{ color: 'var(--text-muted)' }}>Drift: <span style={{ color: STATUS_COLORS[d?.node_status], fontWeight: 700 }}>{d?.drift_score?.toFixed(3)}</span></div>
            <div style={{ color: 'var(--text-muted)' }}>Status: <span style={{ color: STATUS_COLORS[d?.node_status] }}>{d?.node_status}</span></div>
        </div>
    );
};

export default function DriftTimeline() {
    const { selectedRunId, apiBase, setView } = useApp();
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(false);

    const load = useCallback(async () => {
        if (!selectedRunId) return;
        setLoading(true);
        try {
            const r = await fetch(`${apiBase}/runs/${selectedRunId}/drift`);
            const d = await r.json();
            setData(d.drift_timeline || []);
        } catch (_) { }
        setLoading(false);
    }, [selectedRunId, apiBase]);

    useEffect(() => { load(); }, [load]);

    const maxDrift = Math.max(...data.map(d => d.drift_score || 0));
    const avgDrift = data.length ? (data.reduce((s, d) => s + (d.drift_score || 0), 0) / data.length).toFixed(3) : 0;
    const criticalPoints = data.filter(d => d.drift_score > 0.6).length;
    const worstStep = data.reduce((worst, d) => (!worst || d.drift_score > worst.drift_score) ? d : worst, null);

    return (
        <div className="fade-in">
            <div style={{ marginBottom: 16 }}>
                <h2 style={{ marginBottom: 4 }}>Drift Timeline</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    Per-run drift scores across all steps — area chart with clickable anomaly points
                </p>
            </div>

            {/* Summary cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
                {[
                    { label: 'Avg Drift', value: avgDrift, color: 'var(--accent-blue)' },
                    { label: 'Max Drift', value: maxDrift.toFixed(3), color: maxDrift > 0.6 ? 'var(--status-critical)' : maxDrift > 0.35 ? 'var(--status-significant)' : 'var(--status-minor)' },
                    { label: 'Critical Points', value: criticalPoints, color: criticalPoints > 0 ? 'var(--status-critical)' : 'var(--status-verified)' },
                    { label: 'Worst Step', value: worstStep ? `#${worstStep.step_index}` : '—', color: 'var(--status-significant)' },
                ].map(({ label, value, color }) => (
                    <div key={label} className="metric-card">
                        <div className="label">{label}</div>
                        <div className="value" style={{ color }}>{value}</div>
                    </div>
                ))}
            </div>

            <div className="card">
                <div className="card-header">
                    <h3>Drift Score Over Steps</h3>
                    <div style={{ display: 'flex', gap: 12, fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        <span style={{ color: 'var(--status-critical)' }}>── Critical threshold (0.60)</span>
                        <span style={{ color: 'var(--status-significant)' }}>── Significant (0.35)</span>
                        <span style={{ color: 'var(--status-minor)' }}>── Minor (0.15)</span>
                    </div>
                </div>
                <div className="card-body" style={{ padding: '20px 0' }}>
                    {loading ? (
                        <div className="skeleton" style={{ height: 300, margin: '0 20px' }}></div>
                    ) : data.length ? (
                        <ResponsiveContainer width="100%" height={340}>
                            <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="driftGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#63b3ed" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#63b3ed" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                <XAxis dataKey="step_index" stroke="var(--text-muted)" tick={{ fontSize: 11 }} label={{ value: 'Step', position: 'insideBottomRight', fill: 'var(--text-muted)', fontSize: 11 }} />
                                <YAxis stroke="var(--text-muted)" tick={{ fontSize: 11 }} domain={[0, 1]} tickFormatter={v => v.toFixed(2)} />
                                <Tooltip content={<CustomTooltip />} />
                                <ReferenceLine y={0.60} stroke="rgba(245,101,101,0.6)" strokeDasharray="4 4" label={{ value: '0.60', fill: '#f56565', fontSize: 10 }} />
                                <ReferenceLine y={0.35} stroke="rgba(237,137,54,0.5)" strokeDasharray="4 4" label={{ value: '0.35', fill: '#ed8936', fontSize: 10 }} />
                                <ReferenceLine y={0.15} stroke="rgba(236,201,75,0.4)" strokeDasharray="4 4" label={{ value: '0.15', fill: '#ecc94b', fontSize: 10 }} />
                                <Area
                                    type="monotone"
                                    dataKey="drift_score"
                                    stroke="#63b3ed"
                                    strokeWidth={2}
                                    fill="url(#driftGrad)"
                                    dot={<CustomDot />}
                                    activeDot={{ r: 6, fill: '#63b3ed', stroke: 'var(--bg-card)', strokeWidth: 2 }}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : (
                        <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                            No drift data available for this run
                        </div>
                    )}
                </div>
            </div>

            {/* Worst drift points table */}
            {data.length > 0 && (
                <div className="card" style={{ marginTop: 16 }}>
                    <div className="card-header"><h3>Highest Drift Steps</h3></div>
                    <div className="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Step</th>
                                    <th>Tool</th>
                                    <th>Drift Score</th>
                                    <th>Status</th>
                                    <th>Bar</th>
                                </tr>
                            </thead>
                            <tbody>
                                {[...data].sort((a, b) => b.drift_score - a.drift_score).slice(0, 8).map(d => (
                                    <tr key={d.receipt_id}>
                                        <td className="mono">#{d.step_index}</td>
                                        <td style={{ fontWeight: 600 }}>{d.tool_name}</td>
                                        <td style={{ color: STATUS_COLORS[d.node_status], fontWeight: 700 }}>{d.drift_score.toFixed(3)}</td>
                                        <td><span className={`badge badge-${d.node_status?.includes('issue') ? d.node_status.replace('_issue', '') : d.node_status}`}>{d.node_status}</span></td>
                                        <td style={{ width: 120 }}>
                                            <div className="drift-bar-track">
                                                <div
                                                    className="drift-bar-fill"
                                                    style={{
                                                        width: `${(d.drift_score * 100).toFixed(0)}%`,
                                                        background: STATUS_COLORS[d.node_status] || '#4a5568'
                                                    }}
                                                />
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}
