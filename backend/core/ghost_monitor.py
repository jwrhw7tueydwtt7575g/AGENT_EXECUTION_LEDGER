"""
Ghost Call Monitor.
For ReAct-style frameworks that may describe a tool call in the reasoning
chain without ever firing it.

How it works:
 1. InterceptRouter pre-registers every EXPECTED call (parsed from reasoning).
 2. InterceptRouter post-registers every ACTUALLY FIRED call.
 3. At run completion, reconcile() surfaces the delta as ghost calls.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Set


@dataclass
class GhostCallRecord:
    intercept_id: str
    run_id: str
    tool_name: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reasoning_context: str = ""


class GhostCallMonitor:
    """Thread-safe ghost call tracker per run."""

    def __init__(self):
        self._expected: Dict[str, Set[str]] = {}   # run_id -> {intercept_ids}
        self._fired: Dict[str, Set[str]] = {}
        self._tool_map: Dict[str, str] = {}         # intercept_id -> tool_name

    def register_expected(self, run_id: str, tool_name: str, intercept_id: str):
        self._expected.setdefault(run_id, set()).add(intercept_id)
        self._tool_map[intercept_id] = tool_name

    def register_fired(self, run_id: str, tool_name: str, intercept_id: str):
        self._fired.setdefault(run_id, set()).add(intercept_id)

    def reconcile(self, run_id: str) -> List[GhostCallRecord]:
        """Return list of calls that were expected but never fired."""
        expected = self._expected.get(run_id, set())
        fired = self._fired.get(run_id, set())
        ghosts = expected - fired
        return [
            GhostCallRecord(
                intercept_id=iid,
                run_id=run_id,
                tool_name=self._tool_map.get(iid, "unknown"),
            )
            for iid in ghosts
        ]

    def ghost_receipt_for(self, ghost: GhostCallRecord) -> dict:
        """Build a minimal ghost receipt document for the ledger."""
        from core.intercept import sha256, _serialise
        receipt_id = str(uuid.uuid4())
        return {
            "receipt_id": receipt_id,
            "run_id": ghost.run_id,
            "tool_name": ghost.tool_name,
            "agent_id": "unknown",
            "status": "ghost",
            "node_status": "ghost",
            "timestamp": ghost.detected_at,
            "input_payload": {},
            "output_payload": None,
            "input_hash": sha256("ghost"),
            "output_hash": None,
            "chain_hash": sha256(receipt_id),
            "drift_score": None,
            "latency_ms": None,
            "anomaly_flags": ["ghost_call_detected"],
            "failure_types": ["F3"],
            "enrichment_complete": True,
        }
