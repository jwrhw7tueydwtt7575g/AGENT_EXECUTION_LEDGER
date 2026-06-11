import asyncio
import json
import random
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import connect_db, close_db, get_db
from models import RunComparisonRequest
from core.blame_engine import BlameAttributionEngine
from core.receipt_factory import ReceiptFactory
from core.intercept import sha256, _serialise

_blame_engine = BlameAttributionEngine()

app = FastAPI(title="Agent Execution Ledger API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        data = json.dumps(message, default=str)
        dead = set()
        for ws in self.active_connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self.active_connections -= dead


manager = ConnectionManager()


# --- Lifecycle ---
@app.on_event("startup")
async def startup_event():
    await connect_db()
    # Start live background simulator (DISABLED for real testing)
    # asyncio.create_task(live_event_emitter())
    pass


@app.on_event("shutdown")
async def shutdown():
    await close_db()

@app.post("/internal/broadcast")
async def internal_broadcast(payload: dict):
    """Hidden webhook endpoint to allow external python test scripts to trigger live WS dashboard updates."""
    await manager.broadcast(payload)
    return {"status": "broadcasted"}


# --- REST Endpoints ---

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/runs")
async def get_runs(limit: int = Query(20, ge=1, le=100), skip: int = Query(0, ge=0)):
    db = get_db()
    cursor = db.runs.find({}, {"_id": 0}).sort("started_at", -1).skip(skip).limit(limit)
    runs = await cursor.to_list(length=limit)
    return {"runs": runs, "total": await db.runs.count_documents({})}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    db = get_db()
    run = await db.runs.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/runs/{run_id}/receipts")
async def get_receipts(run_id: str):
    db = get_db()
    cursor = db.receipts.find({"run_id": run_id}, {"_id": 0}).sort("step_index", 1)
    receipts = await cursor.to_list(length=1000)
    return {"receipts": receipts, "count": len(receipts)}


@app.get("/receipts/{receipt_id}")
async def get_receipt(receipt_id: str):
    db = get_db()
    receipt = await db.receipts.find_one({"receipt_id": receipt_id}, {"_id": 0})
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@app.get("/runs/{run_id}/drift")
async def get_drift_timeline(run_id: str):
    db = get_db()
    cursor = db.receipts.find(
        {"run_id": run_id, "drift_score": {"$ne": None}},
        {"_id": 0, "step_index": 1, "receipt_id": 1, "tool_name": 1, "drift_score": 1, "timestamp": 1, "node_status": 1}
    ).sort("step_index", 1)
    points = await cursor.to_list(length=1000)
    return {"drift_timeline": points}


@app.post("/runs/compare")
async def compare_runs(req: RunComparisonRequest):
    db = get_db()
    run_a = await db.runs.find_one({"run_id": req.run_id_a}, {"_id": 0})
    run_b = await db.runs.find_one({"run_id": req.run_id_b}, {"_id": 0})
    if not run_a or not run_b:
        raise HTTPException(status_code=404, detail="One or both runs not found")

    receipts_a = await db.receipts.find({"run_id": req.run_id_a}, {"_id": 0}).sort("step_index", 1).to_list(1000)
    receipts_b = await db.receipts.find({"run_id": req.run_id_b}, {"_id": 0}).sort("step_index", 1).to_list(1000)

    max_steps = max(len(receipts_a), len(receipts_b))
    diff_steps = []
    for i in range(max_steps):
        a = receipts_a[i] if i < len(receipts_a) else None
        b = receipts_b[i] if i < len(receipts_b) else None
        diverged = False
        if a and b:
            diverged = (a["tool_name"] != b["tool_name"] or
                        a["output_hash"] != b["output_hash"] or
                        a["node_status"] != b["node_status"])
        diff_steps.append({
            "step_index": i,
            "run_a": a,
            "run_b": b,
            "diverged": diverged
        })

    return {
        "run_a": run_a,
        "run_b": run_b,
        "diff": diff_steps,
        "total_diverged": sum(1 for s in diff_steps if s["diverged"])
    }


@app.get("/anomalies")
async def get_anomalies(limit: int = Query(50, ge=1, le=200)):
    db = get_db()
    cursor = db.receipts.find(
        {"$or": [{"anomaly_flags": {"$ne": []}}, {"node_status": {"$in": ["critical", "significant_issue", "ghost"]}}]},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit)
    anomalies = await cursor.to_list(length=limit)
    return {"anomalies": anomalies, "count": len(anomalies)}


# --- Chain Verification ---

@app.get("/runs/{run_id}/verify-chain")
async def verify_chain(run_id: str):
    """
    Replay SHA-256 chain hashes from scratch.
    Returns whether every receipt's chain_hash is cryptographically consistent.
    Detects F7: Tampered Replay.
    """
    db = get_db()
    receipts = await db.receipts.find(
        {"run_id": run_id}, {"_id": 0}
    ).sort("step_index", 1).to_list(1000)

    if not receipts:
        raise HTTPException(status_code=404, detail="No receipts found for run")

    factory = ReceiptFactory(run_id)
    is_valid = factory.verify_chain(receipts)
    tampered_at = None

    if not is_valid:
        # Find the first mismatch
        prev = sha256(run_id)
        for r in receipts:
            components = {
                "receipt_id": r["receipt_id"], "run_id": r["run_id"],
                "step_index": r["step_index"], "tool_name": r["tool_name"],
                "agent_id": r["agent_id"],
                "timestamp": r["timestamp"].isoformat() if hasattr(r["timestamp"], "isoformat") else r["timestamp"],
                "input_hash": r["input_hash"], "output_hash": r.get("output_hash") or "",
                "status": r["status"], "prev_chain_hash": prev,
            }
            expected = sha256(_serialise(components))
            if expected != r["chain_hash"]:
                tampered_at = r["step_index"]
                break
            prev = r["chain_hash"]

    return {
        "run_id": run_id,
        "chain_valid": is_valid,
        "total_receipts": len(receipts),
        "tampered_at_step": tampered_at,
        "failure_type": "F7" if not is_valid else None,
    }


# --- Blame Attribution / Causal Graph ---

@app.get("/runs/{run_id}/blame")
async def blame_attribution(run_id: str):
    """
    Causal blame attribution: which step caused the final wrong output?
    Returns per-receipt causal_contribution scores and the top-blame receipt.
    """
    db = get_db()
    receipts = await db.receipts.find(
        {"run_id": run_id}, {"_id": 0}
    ).sort("step_index", 1).to_list(1000)

    if not receipts:
        raise HTTPException(status_code=404, detail="No receipts found")

    causal_graph = _blame_engine.build_causal_graph(receipts)
    enriched = _blame_engine.enrich_receipts_with_contributions(receipts)

    # Persist contribution scores back to DB
    for r in enriched:
        await db.receipts.update_one(
            {"receipt_id": r["receipt_id"]},
            {"$set": {"causal_contribution": r["causal_contribution"]}}
        )

    return causal_graph


# --- Universal HTTP Proxy Adapter endpoint ---

class ProxyRequest(BaseModel):
    tool_name: str
    input_body: Dict[str, Any]
    forward_url: Optional[str] = None


@app.post("/proxy")
async def proxy_tool_call(
    req: ProxyRequest,
    x_agent_id: Optional[str] = Header(default="proxy/unknown", alias="X-Agent-ID"),
    x_run_id: Optional[str] = Header(default=None, alias="X-Run-ID"),
    x_permission_scope: Optional[str] = Header(default="read", alias="X-Permission-Scope"),
):
    """
    Universal HTTP Proxy Adapter.
    Any language/framework routes tool calls through here.
    Records request, returns response + X-Receipt-ID header.
    """
    import httpx
    run_id = x_run_id or str(uuid.uuid4())
    db = get_db()
    receipt_id = str(uuid.uuid4())

    input_hash = sha256(_serialise(req.input_body))
    timestamp = datetime.now(timezone.utc)

    # Forward to actual tool endpoint if provided
    output = {"proxied": True, "tool": req.tool_name}
    status = "success"
    latency_ms = 0.0
    start = asyncio.get_event_loop().time()

    if req.forward_url:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(req.forward_url, json=req.input_body)
                output = resp.json()
                status = "success" if resp.status_code < 400 else "error"
        except Exception as e:
            output = {"error": str(e)}
            status = "error"
    latency_ms = (asyncio.get_event_loop().time() - start) * 1000

    output_hash = sha256(_serialise(output))
    # Build chain hash stub (single-receipt proxy calls)
    chain_hash = sha256(sha256(run_id) + input_hash + output_hash)

    receipt_doc = {
        "receipt_id": receipt_id,
        "run_id": run_id,
        "step_index": 0,
        "tool_name": req.tool_name,
        "agent_id": x_agent_id,
        "framework": "HTTP/Proxy",
        "timestamp": timestamp,
        "input_payload": req.input_body,
        "output_payload": output,
        "input_hash": input_hash,
        "output_hash": output_hash,
        "chain_hash": chain_hash,
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "permission_scope": x_permission_scope,
        "anomaly_flags": [],
        "failure_types": [],
        "node_status": "pending",
        "enrichment_complete": False,
    }
    await db.receipts.insert_one(receipt_doc)
    await manager.broadcast({"type": "new_receipt", "receipt":
        {k: v for k, v in receipt_doc.items() if k != "_id"}})

    from fastapi.responses import JSONResponse as JR
    return JR(
        content={"receipt_id": receipt_id, "response": output, "status": status},
        headers={"X-Receipt-ID": receipt_id}
    )


# --- Run Summary update after completion ---

@app.post("/runs/{run_id}/summarise")
async def summarise_run(run_id: str):
    """Recompute and persist run-level aggregates after all receipts are written."""
    db = get_db()
    receipts = await db.receipts.find({"run_id": run_id}, {"_id": 0}).to_list(1000)
    if not receipts:
        raise HTTPException(status_code=404, detail="Run not found")

    drift_scores = [r["drift_score"] for r in receipts if r.get("drift_score") is not None]
    ghost_calls = sum(1 for r in receipts if r.get("status") == "ghost")
    anomaly_count = sum(len(r.get("anomaly_flags", [])) for r in receipts)
    failure_summary: Dict[str, int] = {}
    for r in receipts:
        for ft in r.get("failure_types", []):
            failure_summary[ft] = failure_summary.get(ft, 0) + 1

    factory = ReceiptFactory(run_id)
    chain_verified = factory.verify_chain(receipts)
    trust_score = round(
        1.0
        - (sum(drift_scores) / len(drift_scores) if drift_scores else 0)
        - ghost_calls * 0.05
        - anomaly_count * 0.005,
        4
    )

    update = {
        "total_receipts": len(receipts),
        "total_steps": len(receipts),
        "avg_drift": round(sum(drift_scores) / len(drift_scores), 4) if drift_scores else 0,
        "max_drift": round(max(drift_scores), 4) if drift_scores else 0,
        "ghost_calls": ghost_calls,
        "anomaly_count": anomaly_count,
        "failure_summary": failure_summary,
        "chain_verified": chain_verified,
        "trust_score": max(0, min(1, trust_score)),
        "run_status": "completed",
    }
    await db.runs.update_one({"run_id": run_id}, {"$set": update}, upsert=True)
    return {"run_id": run_id, **update}


@app.get("/stats")
async def get_stats():
    db = get_db()
    total_runs = await db.runs.count_documents({})
    total_receipts = await db.receipts.count_documents({})
    critical_count = await db.receipts.count_documents({"node_status": "critical"})
    ghost_count = await db.receipts.count_documents({"status": "ghost"})
    anomalous_count = await db.receipts.count_documents({"anomaly_flags": {"$ne": []}})

    pipeline = [{"$group": {"_id": None, "avg": {"$avg": "$avg_drift"}, "avg_trust": {"$avg": "$trust_score"}}}]
    agg = await db.runs.aggregate(pipeline).to_list(1)
    avg_drift = round(agg[0]["avg"], 4) if agg else 0
    avg_trust = round(agg[0]["avg_trust"], 4) if agg else 0

    failure_pipeline = [
        {"$unwind": "$failure_types"},
        {"$group": {"_id": "$failure_types", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    failure_dist = await db.receipts.aggregate(failure_pipeline).to_list(20)

    return {
        "total_runs": total_runs,
        "total_receipts": total_receipts,
        "critical_nodes": critical_count,
        "ghost_calls": ghost_count,
        "anomalous_receipts": anomalous_count,
        "avg_drift_across_runs": avg_drift,
        "avg_trust_score": avg_trust,
        "failure_distribution": failure_dist
    }


# --- WebSocket Live Feed ---

TOOLS = ["github_search", "web_browser", "code_executor", "file_reader", "api_caller",
         "data_validator", "memory_store", "llm_reasoner", "sql_query", "vector_search"]
AGENTS = ["PlannerAgent", "ResearchAgent", "CodeAgent", "ValidatorAgent", "ReportAgent"]
STATUSES = ["success", "success", "success", "timeout", "error", "ghost"]
NODE_STATUSES = ["verified", "verified", "verified", "minor_issue", "significant_issue", "critical", "ghost"]


async def live_event_emitter():
    """Background task: emits a new tool call receipt every 2 seconds to all WS clients."""
    await asyncio.sleep(2)
    live_run_id = str(uuid.uuid4())
    step = 0
    prev_chain_hash = hashlib.sha256(live_run_id.encode()).hexdigest()

    while True:
        await asyncio.sleep(2.5)
        tool_name = random.choice(TOOLS)
        agent_id = random.choice(AGENTS)
        status = random.choices(STATUSES, weights=[60, 10, 10, 10, 5, 5])[0]
        drift = round(random.betavariate(2, 8), 3) if status != "ghost" else None
        latency = max(50, random.gauss(420, 120))
        node_status = random.choices(
            NODE_STATUSES,
            weights=[50, 15, 10, 10, 5, 5, 5]
        )[0] if status != "ghost" else "ghost"

        input_data = {"tool": tool_name, "agent": agent_id, "step": step, "ts": datetime.now(timezone.utc).isoformat()}
        input_hash = hashlib.sha256(json.dumps(input_data, sort_keys=True).encode()).hexdigest()
        output_hash = hashlib.sha256(f"output_{step}".encode()).hexdigest() if status != "ghost" else None
        chain_hash = hashlib.sha256((prev_chain_hash + input_hash + (output_hash or "")).encode()).hexdigest()
        prev_chain_hash = chain_hash

        event = {
            "type": "new_receipt",
            "receipt": {
                "receipt_id": str(uuid.uuid4()),
                "run_id": live_run_id,
                "step_index": step,
                "tool_name": tool_name,
                "agent_id": agent_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "node_status": node_status,
                "drift_score": drift,
                "latency_ms": round(latency, 2),
                "input_hash": input_hash,
                "output_hash": output_hash,
                "chain_hash": chain_hash,
                "anomaly_flags": ["confidence_inflation"] if drift and drift > 0.5 else [],
                "failure_types": ["F5"] if drift and drift > 0.5 else []
            }
        }
        await manager.broadcast(event)
        step += 1


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send existing recent receipts first
        db = get_db()
        cursor = db.receipts.find({}, {"_id": 0}).sort("timestamp", -1).limit(30)
        recent = await cursor.to_list(length=30)
        for r in reversed(recent):
            await websocket.send_text(json.dumps({"type": "backfill", "receipt": r}, default=str))
        # Hold connection open
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
