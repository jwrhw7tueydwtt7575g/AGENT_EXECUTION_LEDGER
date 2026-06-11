import React, { useState, useEffect } from 'react';
import { useApp } from '../AppContext';

const STATUS_COLORS = {
    verified: '#48bb78',
    minor_issue: '#ecc94b',
    significant_issue: '#ed8936',
    critical: '#f56565',
    ghost: '#666',
    pending: '#4a5568',
};

function RunSelect({ label, value, onChange, runs }) {
    return (
        <div>
            <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 6 }}>{label}</div>
            <select value={value} onChange={e => onChange(e.target.value)} style={{ width: '100%' }}>
                {runs.map(r => (
                    <option key={r.run_id} value={r.run_id}>
                        {r.run_id.slice(0, 8)}... • {r.agent_name} • {r.framework} • {r.total_steps} steps
                    </option>
                ))}
            </select>
        </div>
    );
}

function CellStatus({ receipt }) {
    if (!receipt) return <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>—</span>;
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className={`node-dot ${receipt.node_status}`}></span>
                <span style={{ fontWeight: 600, fontSize: '0.82rem' }}>{receipt.tool_name}</span>
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {receipt.agent_id} • {receipt.latency_ms?.toFixed(0)}ms
                {receipt.drift_score != null && ` • drift ${receipt.drift_score.toFixed(2)}`}
            </div>
        </div>
    );
}

export default function RunComparison() {
    const { runs, apiBase } = useApp();
    const [runIdA, setRunIdA] = useState('');
    const [runIdB, setRunIdB] = useState('');
    const [diffResult, setDiffResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (runs.length >= 2 && !runIdA) {
            setRunIdA(runs[0].run_id);
            setRunIdB(runs[1].run_id);
        }
    }, [runs]);

    const compare = async () => {
        if (!runIdA || !runIdB || runIdA === runIdB) {
            setError('Please select two different runs');
            return;
        }
        setError('');
        setLoading(true);
        try {
            const r = await fetch(`${apiBase}/runs/compare`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ run_id_a: runIdA, run_id_b: runIdB })
            });
            setDiffResult(await r.json());
        } catch (e) {
            setError('Failed to load comparison');
        }
        setLoading(false);
    };

    useEffect(() => {
        if (runIdA && runIdB && runIdA !== runIdB) compare();
    }, [runIdA, runIdB]);

    const divergedSteps = diffResult?.diff?.filter(s => s.diverged).length || 0;
    const totalSteps = diffResult?.diff?.length || 0;
    const similarity = totalSteps ? ((1 - divergedSteps / totalSteps) * 100).toFixed(1) : null;

    return (
        <div className="fade-in">
            <div style={{ marginBottom: 16 }}>
                <h2 style={{ marginBottom: 4 }}>Run Comparison</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    Side-by-side diff of two runs — highlights where execution paths diverged
                </p>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
                <div className="card-body">
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 12 }}>
                        <RunSelect label="Run A" value={runIdA} onChange={setRunIdA} runs={runs} />
                        <RunSelect label="Run B" value={runIdB} onChange={setRunIdB} runs={runs} />
                    </div>
                    {error && <div style={{ color: 'var(--status-critical)', fontSize: '0.8rem' }}>{error}</div>}
                    {diffResult && (
                        <div style={{ display: 'flex', gap: 20, marginTop: 12, flexWrap: 'wrap' }}>
                            {[
                                { label: 'Total Steps Compared', value: totalSteps },
                                { label: 'Diverged Steps', value: divergedSteps, color: divergedSteps > 0 ? 'var(--status-critical)' : 'var(--status-verified)' },
                                { label: 'Similarity', value: `${similarity}%`, color: similarity > 80 ? 'var(--status-verified)' : 'var(--status-significant)' },
                            ].map(({ label, value, color }) => (
                                <div key={label} className="metric-card" style={{ flex: 1, minWidth: 120 }}>
                                    <div className="label">{label}</div>
                                    <div className="value" style={{ color: color || 'var(--text-primary)', fontSize: '1.4rem' }}>{value}</div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {loading && (
                <div style={{ display: 'flex', gap: 12 }}>
                    {[...Array(6)].map((_, i) => <div key={i} className="skeleton" style={{ flex: 1, height: 48, borderRadius: 8 }}></div>)}
                </div>
            )}

            {diffResult && !loading && (
                <div className="card">
                    <div className="card-header">
                        <h3>Step-by-Step Diff</h3>
                        <div style={{ display: 'flex', gap: 12, fontSize: '0.72rem' }}>
                            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <span style={{ width: 10, height: 10, borderRadius: 2, background: 'rgba(245,101,101,0.2)', display: 'inline-block' }}></span> Diverged
                            </span>
                            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                <span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--bg-secondary)', display: 'inline-block' }}></span> Matching
                            </span>
                        </div>
                    </div>
                    <div>
                        {/* Header */}
                        <div style={{ display: 'grid', gridTemplateColumns: '48px 1fr 1fr', gap: 1, background: 'var(--bg-secondary)', padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
                            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>Step</div>
                            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--accent-blue)' }}>Run A</div>
                            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--accent-purple)' }}>Run B</div>
                        </div>
                        <div style={{ maxHeight: 520, overflowY: 'auto' }}>
                            {diffResult.diff.map((step) => (
                                <div
                                    key={step.step_index}
                                    style={{
                                        display: 'grid', gridTemplateColumns: '48px 1fr 1fr', gap: 1,
                                        background: step.diverged ? 'rgba(245,101,101,0.05)' : 'transparent',
                                        borderLeft: step.diverged ? '3px solid var(--status-critical)' : '3px solid transparent',
                                        borderBottom: '1px solid var(--border)',
                                        padding: '10px 14px',
                                    }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', fontFamily: 'JetBrains Mono', fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700 }}>
                                        #{step.step_index}
                                        {step.diverged && <span style={{ marginLeft: 4, fontSize: '0.6rem', color: 'var(--status-critical)' }}>✕</span>}
                                    </div>
                                    <CellStatus receipt={step.run_a} />
                                    <CellStatus receipt={step.run_b} />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
