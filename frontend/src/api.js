const envApi = import.meta.env.VITE_API_BASE;
const envWs = import.meta.env.VITE_WS_URL;

export function getApiBase() {
    if (envApi) return envApi.replace(/\/$/, '');
    if (typeof window !== 'undefined') return '/api';
    return 'http://localhost:8000';
}

export function getWsUrl() {
    if (envWs) return envWs;
    if (typeof window !== 'undefined') {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${proto}//${window.location.host}/ws/live`;
    }
    return 'ws://localhost:8000/ws/live';
}

export async function apiFetch(path, options = {}) {
    const base = getApiBase();
    const url = path.startsWith('http') ? path : `${base}${path}`;
    const headers = { ...options.headers };
    const apiKey = import.meta.env.VITE_API_KEY;
    if (apiKey) headers['X-API-Key'] = apiKey;

    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail = body.detail;
        const message = typeof detail === 'string' ? detail : `HTTP ${res.status}`;
        throw new Error(message);
    }
    return res.json();
}

export function upsertReceipts(existing, receipt, max = 500) {
    const idx = existing.findIndex(r => r.receipt_id === receipt.receipt_id);
    let updated;
    if (idx >= 0) {
        updated = [...existing];
        updated[idx] = { ...updated[idx], ...receipt };
    } else {
        updated = [...existing, receipt];
    }
    return updated
        .sort((a, b) => (a.step_index ?? 0) - (b.step_index ?? 0))
        .slice(-max);
}
