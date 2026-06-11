import React, { useState, useEffect, useCallback } from 'react';
import ReactFlow, {
    Background, Controls, MiniMap,
    useNodesState, useEdgesState,
    MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useApp } from '../AppContext';

const STATUS_COLORS = {
    verified: '#48bb78',
    minor_issue: '#ecc94b',
    significant_issue: '#ed8936',
    critical: '#f56565',
    ghost: '#333',
    pending: '#4a5568',
};
const STATUS_LABELS = {
    verified: 'Verified',
    minor_issue: 'Minor Issue',
    significant_issue: 'Significant',
    critical: 'Critical',
    ghost: 'Ghost',
    pending: 'Pending',
};

function buildNodesEdges(receipts) {
    const nodes = receipts.map((r, idx) => ({
        id: r.receipt_id,
        position: { x: (idx % 5) * 200 + 40, y: Math.floor(idx / 5) * 140 + 40 },
        data: {
            label: (
                <div style={{ textAlign: 'center', lineHeight: 1.4 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#e8eaf2', marginBottom: 2 }}>{r.tool_name}</div>
                    <div style={{ fontSize: 9, color: '#8892a4' }}>{r.agent_id}</div>
                    <div style={{ fontSize: 9, color: STATUS_COLORS[r.node_status] || '#a0aec0', marginTop: 3 }}>
                        {r.drift_score != null ? `drift ${r.drift_score.toFixed(2)}` : r.status}
                    </div>
                </div>
            ),
            receipt: r
        },
        style: {
            background: r.node_status === 'ghost'
                ? 'rgba(30,30,30,0.8)'
                : `rgba(${hexToRgb(STATUS_COLORS[r.node_status] || '#4a5568')}, 0.08)`,
            border: r.node_status === 'ghost'
                ? '2px dashed #666'
                : `2px solid ${STATUS_COLORS[r.node_status] || '#4a5568'}`,
            borderRadius: 10,
            padding: '8px 12px',
            width: 160,
            boxShadow: r.node_status === 'critical'
                ? `0 0 16px rgba(245,101,101,0.35)`
                : r.node_status === 'verified' ? `0 0 8px rgba(72,187,120,0.2)` : 'none',
        }
    }));

    const edges = receipts.slice(1).map((r, idx) => ({
        id: `e-${idx}`,
        source: receipts[idx].receipt_id,
        target: r.receipt_id,
        style: { stroke: '#2d3748', strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#2d3748' },
        animated: r.node_status === 'critical',
    }));

    return { nodes, edges };
}

function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? `${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)}` : '74,85,104';
}

export default function DagExplorer() {
    const { selectedRunId, apiBase, liveReceipts, runs } = useApp();
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedReceipt, setSelectedReceipt] = useState(null);
    const [loading, setLoading] = useState(false);
    const [mode, setMode] = useState('run'); // 'run' | 'live'

    const loadRun = useCallback(async () => {
        if (!selectedRunId || mode !== 'run') return;
        setLoading(true);
        try {
            const r = await fetch(`${apiBase}/runs/${selectedRunId}/receipts`);
            const d = await r.json();
            const { nodes: n, edges: e } = buildNodesEdges(d.receipts || []);
            setNodes(n); setEdges(e);
        } catch (_) { }
        setLoading(false);
    }, [selectedRunId, apiBase, mode]);

    useEffect(() => { if (mode === 'run') loadRun(); }, [loadRun, mode]);

    useEffect(() => {
        if (mode === 'live' && liveReceipts.length > 0) {
            const sorted = [...liveReceipts].reverse();
            const { nodes: n, edges: e } = buildNodesEdges(sorted.slice(0, 30));
            setNodes(n); setEdges(e);
        }
    }, [liveReceipts, mode]);

    const onNodeClick = (_, node) => setSelectedReceipt(node.data.receipt);

    const currentRun = runs.find(r => r.run_id === selectedRunId);

    return (
        <div className="fade-in">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                    <h2 style={{ marginBottom: 4 }}>Live DAG Explorer</h2>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                        Interactive directed acyclic graph of tool call execution flow
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button className={`btn ${mode === 'run' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setMode('run')}>📦 Historical Run</button>
                    <button className={`btn ${mode === 'live' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setMode('live')}>⚡ Live Feed</button>
                </div>
            </div>

            {/* Legend */}
            <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
                {Object.entries(STATUS_LABELS).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                        <span className={`node-dot ${k}`}></span> {v}
                    </div>
                ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: selectedReceipt ? '1fr 320px' : '1fr', gap: 16 }}>
                <div className="card">
                    <div className="dag-container">
                        {loading ? (
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                                Loading DAG...
                            </div>
                        ) : (
                            <ReactFlow
                                nodes={nodes} edges={edges}
                                onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
                                onNodeClick={onNodeClick}
                                fitView fitViewOptions={{ padding: 0.2 }}
                                attributionPosition="bottom-left"
                            >
                                <Background color="#1a1f2e" gap={24} size={1} />
                                <Controls style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} />
                                <MiniMap
                                    nodeColor={(n) => STATUS_COLORS[n.data?.receipt?.node_status] || '#4a5568'}
                                    style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                                    maskColor="rgba(8,9,13,0.7)"
                                />
                            </ReactFlow>
                        )}
                    </div>
                </div>

                {selectedReceipt && (
                    <div className="card slide-in" style={{ maxHeight: 520, overflowY: 'auto' }}>
                        <div className="card-header">
                            <h3>Receipt Detail</h3>
                            <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={() => setSelectedReceipt(null)}>✕</button>
                        </div>
                        <div className="card-body" style={{ padding: 16 }}>
                            <div style={{ marginBottom: 12 }}>
                                <span className={`badge badge-${selectedReceipt.node_status?.replace('_issue', '') || 'pending'}`}>{selectedReceipt.node_status}</span>
                            </div>
                            {[
                                ['Tool', selectedReceipt.tool_name],
                                ['Agent', selectedReceipt.agent_id],
                                ['Status', selectedReceipt.status],
                                ['Step', selectedReceipt.step_index],
                                ['Latency', `${selectedReceipt.latency_ms?.toFixed(0)} ms`],
                                ['Drift', selectedReceipt.drift_score?.toFixed(3)],
                                ['Confidence', selectedReceipt.confidence_score?.toFixed(3)],
                            ].map(([k, v]) => (
                                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: '0.79rem' }}>
                                    <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                                    <span style={{ fontWeight: 600 }}>{v ?? '—'}</span>
                                </div>
                            ))}
                            {selectedReceipt.anomaly_flags?.length > 0 && (
                                <div style={{ marginTop: 12 }}>
                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Anomaly Flags</div>
                                    {selectedReceipt.anomaly_flags.map(f => (
                                        <span key={f} className="badge badge-critical" style={{ marginRight: 4 }}>{f}</span>
                                    ))}
                                </div>
                            )}
                            <div style={{ marginTop: 12 }}>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Chain Hash</div>
                                <div className="mono" style={{ fontSize: '0.65rem', color: 'var(--accent-cyan)', wordBreak: 'break-all' }}>{selectedReceipt.chain_hash}</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
