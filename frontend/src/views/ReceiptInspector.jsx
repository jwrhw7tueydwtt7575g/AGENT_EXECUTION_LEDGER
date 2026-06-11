import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { useApp } from '../AppContext';

export default function ReceiptInspector() {
    const { selectedRunId, apiBase } = useApp();
    const [receipts, setReceipts] = useState([]);
    const [selected, setSelected] = useState(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!selectedRunId) return;
        setLoading(true);
        fetch(`${apiBase}/runs/${selectedRunId}/receipts`)
            .then(r => r.json())
            .then(d => {
                setReceipts(d.receipts || []);
                if (d.receipts?.length) setSelected(d.receipts[0]);
            })
            .catch(() => { })
            .finally(() => setLoading(false));
    }, [selectedRunId, apiBase]);

    const nodeStatusMap = {
        verified: 'badge-verified',
        minor_issue: 'badge-minor',
        significant_issue: 'badge-significant',
        critical: 'badge-critical',
        ghost: 'badge-ghost',
        pending: 'badge-pending',
    };

    const driftColor = (d) => {
        if (d == null) return 'var(--text-muted)';
        if (d > 0.6) return 'var(--status-critical)';
        if (d > 0.35) return 'var(--status-significant)';
        if (d > 0.15) return 'var(--status-minor)';
        return 'var(--status-verified)';
    };

    return (
        <div className="fade-in">
            <div style={{ marginBottom: 16 }}>
                <h2 style={{ marginBottom: 4 }}>Receipt Inspector</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    Full detail view of individual tool call receipts with hashes, timing, and drift breakdown
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, height: 620 }}>
                {/* Receipt List */}
                <div className="card" style={{ overflowY: 'auto' }}>
                    <div className="card-header" style={{ position: 'sticky', top: 0, background: 'var(--bg-card)', zIndex: 2 }}>
                        <h3>Receipts</h3>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{receipts.length}</span>
                    </div>
                    {loading ? (
                        <div style={{ padding: 20 }}>
                            {[...Array(6)].map((_, i) => (
                                <div key={i} className="skeleton" style={{ height: 52, marginBottom: 8 }}></div>
                            ))}
                        </div>
                    ) : receipts.map(r => (
                        <div
                            key={r.receipt_id}
                            className={`run-item ${selected?.receipt_id === r.receipt_id ? 'selected' : ''}`}
                            onClick={() => setSelected(r)}
                        >
                            <span className={`node-dot ${r.node_status}`}></span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontWeight: 600, fontSize: '0.8rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {r.tool_name}
                                </div>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                    Step {r.step_index} • {r.agent_id}
                                </div>
                            </div>
                            {r.drift_score != null && (
                                <span style={{ fontSize: '0.7rem', fontWeight: 700, color: driftColor(r.drift_score) }}>
                                    {r.drift_score.toFixed(2)}
                                </span>
                            )}
                        </div>
                    ))}
                </div>

                {/* Receipt Detail */}
                {selected ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
                        {/* Header card */}
                        <div className="card">
                            <div className="card-header">
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <span className={`node-dot ${selected.node_status}`}></span>
                                    <h3 style={{ fontSize: '0.95rem' }}>{selected.tool_name}</h3>
                                    <span className={`badge ${nodeStatusMap[selected.node_status] || 'badge-pending'}`}>{selected.node_status}</span>
                                </div>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                    {selected.timestamp ? new Date(selected.timestamp).toLocaleString() : '—'}
                                </span>
                            </div>
                            <div className="card-body">
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                                    {[
                                        { label: 'Latency', value: `${selected.latency_ms?.toFixed(0) ?? '—'} ms` },
                                        { label: 'Drift Score', value: selected.drift_score?.toFixed(3) ?? '—', color: driftColor(selected.drift_score) },
                                        { label: 'Confidence', value: selected.confidence_score?.toFixed(3) ?? '—' },
                                        { label: 'Cache Hit', value: selected.cache_hit ? 'Yes' : 'No', color: selected.staleness_flag ? 'var(--status-minor)' : undefined },
                                    ].map(({ label, value, color }) => (
                                        <div key={label} style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: '12px' }}>
                                            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 6 }}>{label}</div>
                                            <div style={{ fontSize: '1.1rem', fontWeight: 800, color: color || 'var(--text-primary)' }}>{value}</div>
                                        </div>
                                    ))}
                                </div>

                                {selected.anomaly_flags?.length > 0 && (
                                    <div style={{ marginTop: 12, padding: '10px 12px', background: 'rgba(245,101,101,0.07)', borderRadius: 8, border: '1px solid rgba(245,101,101,0.2)' }}>
                                        <span style={{ fontSize: '0.72rem', color: 'var(--status-critical)', fontWeight: 700 }}>⚠ Anomaly Flags: </span>
                                        {selected.anomaly_flags.map(f => <span key={f} style={{ marginLeft: 6, fontSize: '0.75rem' }}>{f}</span>)}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Hash chain */}
                        <div className="card">
                            <div className="card-header"><h3>Hash Chain</h3></div>
                            <div className="card-body">
                                {[
                                    { label: 'Input Hash', val: selected.input_hash },
                                    { label: 'Output Hash', val: selected.output_hash },
                                    { label: 'Chain Hash', val: selected.chain_hash },
                                ].map(({ label, val }) => (
                                    <div key={label} style={{ marginBottom: 10 }}>
                                        <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 3 }}>{label}</div>
                                        <div className="mono" style={{ fontSize: '0.72rem', color: val ? 'var(--accent-cyan)' : 'var(--text-muted)', wordBreak: 'break-all' }}>
                                            {val || 'null — ghost call, no output recorded'}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Input/Output JSON */}
                        <div className="grid-2">
                            <div className="card">
                                <div className="card-header"><h3>Input Payload</h3></div>
                                <div style={{ height: 200 }}>
                                    <Editor
                                        height="200px"
                                        defaultLanguage="json"
                                        value={JSON.stringify(selected.input_payload, null, 2)}
                                        options={{ readOnly: true, minimap: { enabled: false }, fontSize: 11, scrollBeyondLastLine: false, theme: 'vs-dark' }}
                                        theme="vs-dark"
                                    />
                                </div>
                            </div>
                            <div className="card">
                                <div className="card-header"><h3>Output Payload</h3></div>
                                <div style={{ height: 200 }}>
                                    <Editor
                                        height="200px"
                                        defaultLanguage="json"
                                        value={JSON.stringify(selected.output_payload, null, 2)}
                                        options={{ readOnly: true, minimap: { enabled: false }, fontSize: 11, scrollBeyondLastLine: false, theme: 'vs-dark' }}
                                        theme="vs-dark"
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                        <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                            <div style={{ fontSize: '2rem', marginBottom: 12 }}>🔍</div>
                            <div>Select a receipt to inspect</div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
