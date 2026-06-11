import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { getApiBase, getWsUrl, apiFetch, upsertReceipts } from './api';

const AppContext = createContext(null);

export function AppProvider({ children }) {
    const [view, setView] = useState('dag');
    const [runs, setRuns] = useState([]);
    const [selectedRunId, setSelectedRunId] = useState(null);
    const [liveReceipts, setLiveReceipts] = useState([]);
    const [liveReceiptsByRun, setLiveReceiptsByRun] = useState({});
    const [stats, setStats] = useState(null);
    const [wsConnected, setWsConnected] = useState(false);
    const [liveRunId, setLiveRunId] = useState(null);
    const [autoSwitchToLatest, setAutoSwitchToLatest] = useState(true);
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const shouldReconnectRef = useRef(true);
    const knownRunIds = useRef(new Set());

    const fetchRuns = useCallback(async () => {
        try {
            const d = await apiFetch('/runs');
            const fetchedRuns = d.runs || [];
            setRuns(fetchedRuns);
            fetchedRuns.forEach(r => knownRunIds.current.add(r.run_id));
            setSelectedRunId(prev => prev ?? fetchedRuns[0]?.run_id ?? null);
        } catch (e) {
            console.error('fetchRuns error', e);
        }
    }, []);

    const fetchStats = useCallback(async () => {
        try {
            setStats(await apiFetch('/stats'));
        } catch (e) {
            console.error('fetchStats error', e);
        }
    }, []);

    useEffect(() => {
        fetchRuns();
        fetchStats();
        const interval = setInterval(() => { fetchRuns(); fetchStats(); }, 15000);
        return () => clearInterval(interval);
    }, [fetchRuns, fetchStats]);

    useEffect(() => {
        shouldReconnectRef.current = true;
        const apiKey = import.meta.env.VITE_API_KEY;
        const wsQuery = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : '';

        const connect = () => {
            const ws = new WebSocket(`${getWsUrl()}${wsQuery}`);
            wsRef.current = ws;
            ws.onopen = () => setWsConnected(true);
            ws.onclose = () => {
                setWsConnected(false);
                if (shouldReconnectRef.current) {
                    reconnectTimerRef.current = setTimeout(connect, 3000);
                }
            };
            ws.onerror = () => ws.close();
            ws.onmessage = (e) => {
                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'new_receipt' || msg.type === 'backfill') {
                        const receipt = msg.receipt;
                        const rid = receipt.run_id;

                        setLiveReceipts(prev => {
                            const idx = prev.findIndex(r => r.receipt_id === receipt.receipt_id);
                            if (idx >= 0) {
                                const updated = [...prev];
                                updated[idx] = { ...updated[idx], ...receipt };
                                return updated;
                            }
                            return [receipt, ...prev].slice(0, 200);
                        });

                        setLiveReceiptsByRun(prev => ({
                            ...prev,
                            [rid]: upsertReceipts(prev[rid] || [], receipt, 500),
                        }));

                        if (!knownRunIds.current.has(rid)) {
                            knownRunIds.current.add(rid);
                            fetchRuns();
                            fetchStats();
                        }

                        setLiveRunId(rid);
                    }

                    if (msg.type === 'receipt_enriched') {
                        setLiveReceiptsByRun(prev => {
                            const updated = { ...prev };
                            for (const runId of Object.keys(updated)) {
                                updated[runId] = updated[runId].map(r =>
                                    r.receipt_id === msg.receipt_id
                                        ? { ...r, ...msg.updates }
                                        : r
                                );
                            }
                            return updated;
                        });
                        setLiveReceipts(prev =>
                            prev.map(r =>
                                r.receipt_id === msg.receipt_id
                                    ? { ...r, ...msg.updates }
                                    : r
                            )
                        );
                    }
                } catch (_) { }
            };
        };
        connect();
        return () => {
            shouldReconnectRef.current = false;
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            wsRef.current?.close();
        };
    }, [fetchRuns, fetchStats]);

    useEffect(() => {
        if (autoSwitchToLatest && liveRunId && liveRunId !== selectedRunId) {
            setSelectedRunId(liveRunId);
        }
    }, [liveRunId, autoSwitchToLatest, selectedRunId]);

    return (
        <AppContext.Provider value={{
            view, setView,
            runs, selectedRunId, setSelectedRunId,
            liveReceipts, liveReceiptsByRun,
            liveRunId,
            autoSwitchToLatest, setAutoSwitchToLatest,
            wsConnected, stats,
            fetchRuns,
            apiBase: getApiBase(),
        }}>
            {children}
        </AppContext.Provider>
    );
}

export function useApp() {
    const ctx = useContext(AppContext);
    if (!ctx) throw new Error('useApp must be used within AppProvider');
    return ctx;
}
