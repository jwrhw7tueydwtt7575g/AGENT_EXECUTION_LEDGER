"""
Mock data seeder — seeds a MongoDB with realistic Agent ledger receipts
to simulate an AI agent pipeline actively running.
"""
import asyncio
import random
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb+srv://vivekchaudhari3718:vivekchaudhari3718@cluster1.9qlun5j.mongodb.net/?retryWrites=true&w=majority"

DB_NAME = "agent_ledger"

TOOLS = [
    "github_search", "web_browser", "code_executor", "file_reader",
    "api_caller", "data_validator", "memory_store", "llm_reasoner",
    "sql_query", "vector_search", "email_sender", "slack_notifier"
]
AGENTS = ["PlannerAgent", "ResearchAgent", "CodeAgent", "ValidatorAgent", "ReportAgent"]
FRAMEWORKS = ["LangChain", "CrewAI", "AutoGen", "Custom/HTTP"]
FAILURE_TYPES_MAP = {
    "F1": "Silent API Failure",
    "F2": "Timeout Hallucination",
    "F3": "Ghost Tool Call",
    "F4": "Stale Cache Drift",
    "F5": "Multi-Agent Semantic Drift",
    "F6": "Confidence Inflation",
    "F7": "Tampered Replay",
    "F8": "Permission Boundary Violation"
}


def sha256_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def determine_node_status(drift: float, latency: float, avg_latency: float, anomaly_flags: list, status: str) -> str:
    if status == "ghost":
        return "ghost"
    if not drift and not anomaly_flags:
        return "pending"
    std_dev = avg_latency * 0.3
    if drift is None:
        return "pending"
    if drift > 0.60 or len([f for f in anomaly_flags if "hash_mismatch" in f]) > 0:
        return "critical"
    if drift > 0.35 or anomaly_flags:
        return "significant_issue"
    if drift > 0.15 or latency > avg_latency + 2 * std_dev:
        return "minor_issue"
    return "verified"


def generate_receipt(run_id: str, step_index: int, prev_chain_hash: str, avg_latency: float, base_time: datetime) -> dict:
    tool_name = random.choice(TOOLS)
    agent_id = random.choice(AGENTS)
    status = random.choices(["success", "timeout", "error", "ghost"], weights=[75, 10, 10, 5])[0]
    latency_ms = random.gauss(avg_latency, avg_latency * 0.3)
    latency_ms = max(50, latency_ms)
    drift_score = None
    anomaly_flags = []
    failure_types = []
    confidence_score = round(random.uniform(0.5, 1.0), 3)
    cache_hit = random.random() < 0.15
    staleness_flag = cache_hit and random.random() < 0.3

    if status != "ghost":
        drift_score = round(random.betavariate(2, 8), 3)
        if random.random() < 0.12:
            drift_score = round(random.uniform(0.35, 0.85), 3)
            failure_types.append(random.choice(list(FAILURE_TYPES_MAP.keys())))
        if staleness_flag:
            anomaly_flags.append("staleness_detected")
        if confidence_score > 0.9 and drift_score > 0.3:
            anomaly_flags.append("confidence_inflation")
            failure_types.append("F6")

    input_data = {"tool": tool_name, "agent": agent_id, "step": step_index, "args": {"query": f"query_{step_index}"}}
    output_data = {"result": f"result_{step_index}", "status": status} if status != "ghost" else None

    input_hash = sha256_hash(json.dumps(input_data, sort_keys=True))
    output_hash = sha256_hash(json.dumps(output_data, sort_keys=True)) if output_data else None
    chain_hash = sha256_hash(prev_chain_hash + input_hash + (output_hash or ""))

    node_status = determine_node_status(drift_score, latency_ms, avg_latency, anomaly_flags, status)

    timestamp = base_time + timedelta(milliseconds=step_index * avg_latency + random.uniform(-50, 50))

    return {
        "receipt_id": str(uuid.uuid4()),
        "run_id": run_id,
        "step_index": step_index,
        "tool_name": tool_name,
        "agent_id": agent_id,
        "timestamp": timestamp,
        "input_payload": input_data,
        "output_payload": output_data,
        "input_hash": input_hash,
        "output_hash": output_hash,
        "chain_hash": chain_hash,
        "status": status,
        "node_status": node_status,
        "drift_score": drift_score,
        "confidence_score": confidence_score,
        "latency_ms": round(latency_ms, 2),
        "cache_hit": cache_hit,
        "staleness_flag": staleness_flag,
        "anomaly_flags": anomaly_flags,
        "failure_types": list(set(failure_types)),
        "parent_receipt_id": None,
        "children_receipt_ids": [],
        "permission_scope": random.choice(["read", "write", "admin", "restricted"]),
        "enrichment_complete": status != "ghost"
    }


async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    await db.receipts.drop()
    await db.runs.drop()

    print("Seeding Agent Execution Ledger with mock data...")
    num_runs = 6
    avg_latency = 420.0

    for run_idx in range(num_runs):
        run_id = str(uuid.uuid4())
        framework = random.choice(FRAMEWORKS)
        agent_name = random.choice(AGENTS)
        num_steps = random.randint(8, 20)
        base_time = datetime.now(timezone.utc) - timedelta(hours=(num_runs - run_idx) * 4)
        chain_hash = sha256_hash(run_id)

        receipts = []
        for step in range(num_steps):
            receipt = generate_receipt(run_id, step, chain_hash, avg_latency, base_time)
            chain_hash = receipt["chain_hash"]
            receipts.append(receipt)

        await db.receipts.insert_many(receipts)

        drift_scores = [r["drift_score"] for r in receipts if r["drift_score"] is not None]
        ghost_calls = sum(1 for r in receipts if r["status"] == "ghost")
        anomaly_count = sum(len(r["anomaly_flags"]) for r in receipts)
        failure_summary = {}
        for r in receipts:
            for ft in r["failure_types"]:
                failure_summary[ft] = failure_summary.get(ft, 0) + 1

        completed_at = base_time + timedelta(milliseconds=num_steps * avg_latency)
        trust_score = round(1.0 - (sum(drift_scores) / len(drift_scores) if drift_scores else 0) - (ghost_calls * 0.05) - (anomaly_count * 0.01), 3)

        run_doc = {
            "run_id": run_id,
            "agent_name": agent_name,
            "framework": framework,
            "started_at": base_time,
            "completed_at": completed_at,
            "total_steps": num_steps,
            "total_receipts": len(receipts),
            "avg_drift": round(sum(drift_scores) / len(drift_scores), 4) if drift_scores else 0,
            "max_drift": round(max(drift_scores), 4) if drift_scores else 0,
            "chain_verified": random.random() > 0.15,
            "ghost_calls": ghost_calls,
            "anomaly_count": anomaly_count,
            "trust_score": max(0, min(1, trust_score)),
            "run_status": "completed",
            "failure_summary": failure_summary
        }
        await db.runs.insert_one(run_doc)
        print(f"  Run {run_idx+1}/{num_runs}: {run_id[:8]}... ({num_steps} steps, drift avg={run_doc['avg_drift']})")

    await db.receipts.create_index([("run_id", 1), ("timestamp", 1)])
    await db.runs.create_index([("run_id", 1)], unique=True)
    await db.runs.create_index([("started_at", -1)])

    print(f"\nSeeding complete! {num_runs} runs inserted into '{DB_NAME}'.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
