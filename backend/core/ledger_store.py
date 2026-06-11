"""
Ledger Store — The atomic persistence layer.
Writes receipts to MongoDB, triggers enrichment, emits WebSocket events.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from core.intercept import InterceptPoint, sha256, _serialise
from core.drift_engine import SemanticDriftEngine
from core.auditors import PermissionAuditor, ConfidenceInspector
from core.ghost_monitor import GhostCallMonitor


class LedgerStore:
    """
    Persistent atomic ledger.
    All enrichment runs in background tasks — never blocks the agent.
    """

    def __init__(self, db, broadcast_fn: Callable):
        self.db = db
        self.broadcast = broadcast_fn
        self._drift_engine = SemanticDriftEngine()
        self._perm_auditor = PermissionAuditor()
        self._conf_inspector = ConfidenceInspector()
        self._chain_hashes: Dict[str, str] = {}   # run_id -> last chain hash
        self._step_counters: Dict[str, int] = {}  # run_id -> step count

    def _get_prev_hash(self, run_id: str) -> str:
        return self._chain_hashes.get(run_id, sha256(run_id))

    def _advance(self, run_id: str, new_hash: str):
        self._chain_hashes[run_id] = new_hash
        self._step_counters[run_id] = self._step_counters.get(run_id, 0) + 1

    async def record(
        self,
        point: InterceptPoint,
        output: Optional[dict],
        status: str,
        latency_ms: float,
        agent_interpretation: Optional[str] = None,
    ):
        """Atomically build, enrich, and persist a receipt."""
        prev_hash = self._get_prev_hash(point.run_id)
        step = self._step_counters.get(point.run_id, 0)

        input_hash = sha256(_serialise(point.input_payload))
        output_hash = sha256(_serialise(output or {})) if status != "ghost" else None
        receipt_id = str(uuid.uuid4())
        chain_fields = {
            "receipt_id": receipt_id, "run_id": point.run_id, "step_index": step,
            "tool_name": point.tool_name, "agent_id": point.agent_id,
            "timestamp": point.timestamp.isoformat(), "input_hash": input_hash,
            "output_hash": output_hash or "", "status": status, "prev_chain_hash": prev_hash,
        }
        chain_hash = sha256(_serialise(chain_fields))
        self._advance(point.run_id, chain_hash)

        receipt = {
            "receipt_id": receipt_id,
            "run_id": point.run_id,
            "step_index": step,
            "tool_name": point.tool_name,
            "agent_id": point.agent_id,
            "framework": point.framework,
            "timestamp": point.timestamp,
            "input_payload": point.input_payload,
            "output_payload": output,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "chain_hash": chain_hash,
            "status": status,
            "latency_ms": latency_ms,
            "permission_scope": point.permission_scope,
            "parent_receipt_id": point.parent_receipt_id,
            "children_receipt_ids": [],
            "drift_score": None,
            "confidence_score": None,
            "node_status": "pending",
            "anomaly_flags": [],
            "failure_types": [],
            "cache_hit": False,
            "staleness_flag": False,
            "causal_contribution": None,
            "enrichment_complete": False,
        }

        # Atomic insert
        await self.db.receipts.insert_one({**receipt})

        # Aggregation Upsert per Run
        await self.db.runs.update_one(
            {"run_id": point.run_id},
            {
                "$set": {
                    "agent_name": point.agent_id,
                    "framework": point.framework,
                    "last_updated": datetime.utcnow()
                },
                "$setOnInsert": {
                    "started_at": datetime.utcnow(),
                    "ghost_calls": 0,
                    "anomaly_count": 0,
                    "run_status": "running"
                },
                "$inc": {"total_receipts": 1, "total_steps": 1}
            },
            upsert=True
        )

        # Emit raw event immediately (before enrichment)
        asyncio.create_task(self.broadcast({
            "type": "new_receipt",
            "receipt": {k: v for k, v in receipt.items() if k != "_id"}
        }))

        # Async enrichment (non-blocking)
        asyncio.create_task(self._enrich(receipt_id, receipt, agent_interpretation))

        return type("R", (), {"receipt_id": receipt_id})()

    async def _enrich(self, receipt_id: str, receipt: dict, agent_interpretation: Optional[str]):
        """Background enrichment: drift, audits, node status."""
        await asyncio.sleep(0.05)   # yield to event loop

        # Semantic drift
        enriched = self._drift_engine.enrich_receipt(receipt.copy(), agent_interpretation)

        # Permission + confidence audits
        flags, ftypes = self._perm_auditor.audit(enriched)
        confidence, flags2, ftypes2 = self._conf_inspector.inspect(enriched)
        all_flags = list(set(flags + flags2 + enriched.get("anomaly_flags", [])))
        all_ftypes = list(set(ftypes + ftypes2 + enriched.get("failure_types", [])))

        # Node status
        node_status = self._drift_engine.determine_node_status(
            drift=enriched.get("drift_score"),
            latency_ms=receipt.get("latency_ms", 0),
            run_latency_mean=500, run_latency_std=150,
            anomaly_flags=all_flags,
            status=receipt.get("status", "success"),
        )

        update = {
            "drift_score": enriched.get("drift_score"),
            "confidence_score": confidence,
            "anomaly_flags": all_flags,
            "failure_types": all_ftypes,
            "node_status": node_status,
            "enrichment_complete": True,
        }
        await self.db.receipts.update_one({"receipt_id": receipt_id}, {"$set": update})

        # Broadcast enrichment update
        asyncio.create_task(self.broadcast({
            "type": "receipt_enriched",
            "receipt_id": receipt_id,
            "updates": update,
        }))
