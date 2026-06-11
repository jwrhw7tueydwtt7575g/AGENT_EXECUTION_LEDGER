"""
Ledger Store — The atomic persistence layer.
Writes receipts to MongoDB, triggers enrichment, emits WebSocket events.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional, Tuple

from pymongo import ReturnDocument

from core.intercept import InterceptPoint, sha256, _serialise
from core.drift_engine import SemanticDriftEngine
from core.auditors import PermissionAuditor, ConfidenceInspector
from core.anomaly_detector import AnomalyDetector


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
        min_runs = int(os.getenv("ANOMALY_BASELINE_MIN_RUNS", "20"))
        self._anomaly_detector = AnomalyDetector(min_baseline_runs=min_runs)

    async def _allocate_chain_slot(self, run_id: str) -> Tuple[str, int]:
        """Atomically reserve step index and previous chain hash from MongoDB."""
        genesis = sha256(run_id)
        result = await self.db.run_state.find_one_and_update(
            {"run_id": run_id},
            [
                {
                    "$set": {
                        "slot_step": {"$ifNull": ["$next_step", 0]},
                        "slot_prev": {"$ifNull": ["$prev_chain_hash", genesis]},
                    }
                },
                {"$set": {"next_step": {"$add": ["$slot_step", 1]}}},
            ],
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return result["slot_prev"], result["slot_step"]

    async def _commit_chain_hash(self, run_id: str, chain_hash: str):
        await self.db.run_state.update_one(
            {"run_id": run_id},
            {"$set": {"prev_chain_hash": chain_hash}},
        )

    async def record(
        self,
        point: InterceptPoint,
        output: Optional[dict],
        status: str,
        latency_ms: float,
        agent_interpretation: Optional[str] = None,
    ):
        """Atomically build, enrich, and persist a receipt."""
        prev_hash, step = await self._allocate_chain_slot(point.run_id)

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
        await self._commit_chain_hash(point.run_id, chain_hash)

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

        await self.db.receipts.insert_one({**receipt})

        now = datetime.now(timezone.utc)
        await self.db.runs.update_one(
            {"run_id": point.run_id},
            {
                "$set": {
                    "agent_name": point.agent_id,
                    "framework": point.framework,
                    "last_updated": now,
                },
                "$setOnInsert": {
                    "started_at": now,
                    "ghost_calls": 0,
                    "anomaly_count": 0,
                    "run_status": "running",
                },
                "$inc": {"total_receipts": 1, "total_steps": 1},
            },
            upsert=True,
        )

        asyncio.create_task(self._safe_broadcast({
            "type": "new_receipt",
            "receipt": {k: v for k, v in receipt.items() if k != "_id"},
        }))

        asyncio.create_task(self._enrich(receipt_id, receipt, agent_interpretation))

        return type("R", (), {"receipt_id": receipt_id})()

    async def _safe_broadcast(self, message: dict):
        try:
            await self.broadcast(message)
        except Exception as e:
            print(f"Broadcast failed: {e}")

    async def _enrich(self, receipt_id: str, receipt: dict, agent_interpretation: Optional[str]):
        """Background enrichment: drift, audits, node status."""
        try:
            await asyncio.sleep(0.05)

            enriched = self._drift_engine.enrich_receipt(receipt.copy(), agent_interpretation)

            flags, ftypes = self._perm_auditor.audit(enriched)
            confidence, flags2, ftypes2 = self._conf_inspector.inspect(enriched)
            all_flags = list(set(flags + flags2 + enriched.get("anomaly_flags", [])))
            all_ftypes = list(set(ftypes + ftypes2 + enriched.get("failure_types", [])))

            total_runs = await self.db.runs.count_documents({})
            hist_cursor = self.db.receipts.find(
                {"status": {"$ne": "ghost"}},
                {"_id": 0},
            ).limit(5000)
            historical = await hist_cursor.to_list(length=5000)
            self._anomaly_detector.update_baseline(historical)
            anom_flags, anom_ftypes = self._anomaly_detector.flag_anomalies(enriched, total_runs)
            all_flags = list(set(all_flags + anom_flags))
            all_ftypes = list(set(all_ftypes + anom_ftypes))

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

            asyncio.create_task(self._safe_broadcast({
                "type": "receipt_enriched",
                "receipt_id": receipt_id,
                "updates": update,
            }))
        except Exception as e:
            print(f"Enrichment failed for {receipt_id}: {e}")
