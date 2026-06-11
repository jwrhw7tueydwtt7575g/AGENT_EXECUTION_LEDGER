import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/live';

const AppContext = createContext(null);

export function AppProvider({ children }) {
    const [view, setView] = useState('dag');
    const [runs, setRuns] = useState([]);
    const [selectedRunId, setSelectedRunId] = useState(null);
    const [liveReceipts, setLiveReceipts] = useState([]);
    const [stats, setStats] = useState(null);
    const [wsConnected, setWsConnected] = useState(false);
    const wsRef = useRef(null);

    const fetchRuns = useCallback(async () => {
        try {
            const r = await fetch(`${API_BASE}/runs`);
            const d = await r.json();
            setRuns(d.runs || []);
            if (d.runs?.length && !selectedRunId) setSelectedRunId(d.runs[0].run_id);
        } catch (e) { console.error('fetchRuns error', e); }
    }, [selectedRunId]);

    const fetchStats = useCallback(async () => {
        try {
            const r = await fetch(`${API_BASE}/stats`);
            setStats(await r.json());
        } catch (e) { }
    }, []);

    useEffect(() => {
        fetchRuns();
        fetchStats();
        const interval = setInterval(() => { fetchRuns(); fetchStats(); }, 15000);
        return () => clearInterval(interval);
    }, []);

    // WebSocket
    useEffect(() => {
        const connect = () => {
            const ws = new WebSocket(WS_URL);
            wsRef.current = ws;
            ws.onopen = () => setWsConnected(true);
            ws.onclose = () => { setWsConnected(false); setTimeout(connect, 3000); };
            ws.onerror = () => ws.close();
            ws.onmessage = (e) => {
                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'new_receipt' || msg.type === 'backfill') {
                        setLiveReceipts(prev => {
                            const next = [msg.receipt, ...prev].slice(0, 200);
                            return next;
                        });
                    }
                } catch (_) { }
            };
        };
        connect();
        return () => wsRef.current?.close();
    }, []);

    return (
        <AppContext.Provider value={{
            view, setView,
            runs, selectedRunId, setSelectedRunId,
            liveReceipts, wsConnected, stats,
            fetchRuns,
            apiBase: API_BASE
        }}>
            {children}
        </AppContext.Provider>
    );
}

export function useApp() { return useContext(AppContext); }
