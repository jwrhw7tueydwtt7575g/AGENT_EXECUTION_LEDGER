"""
Receipt Factory — builds cryptographically signed ExecutionReceipts
and maintains the SHA-256 chain hash across a run.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from core.intercept import InterceptContext, _serialise, sha256


class ExecutionReceipt:
    """Immutable record of a single tool call execution."""

    def __init__(
        self,
        ctx: InterceptContext,
        prev_chain_hash: str,
        step_index: int,
    ):
        p = ctx.point

        # --- Three-Layer Hash Model ---
        # Layer 1: Input hash — SHA-256 of serialised tool input (sorted keys)
        self.input_hash = sha256(_serialise(p.input_payload))

        # Layer 2: Output hash — SHA-256 of serialised tool output or error obj
        raw_output = ctx.output_payload or {"error": str(ctx.error)} if ctx.error else {}
        self.output_hash = sha256(_serialise(raw_output)) if ctx.status != "ghost" else None

        # Layer 3: Chain hash — SHA-256 of all fields + previous receipt hash
        chain_components = {
            "receipt_id": str(uuid.uuid4()),
            "run_id": p.run_id,
            "step_index": step_index,
            "tool_name": p.tool_name,
            "agent_id": p.agent_id,
            "timestamp": p.timestamp.isoformat(),
            "input_hash": self.input_hash,
            "output_hash": self.output_hash or "",
            "status": ctx.status,
            "prev_chain_hash": prev_chain_hash,
        }
        self.chain_hash = sha256(_serialise(chain_components))

        # --- Core fields ---
        self.receipt_id: str = chain_components["receipt_id"]
        self.run_id: str = p.run_id
        self.step_index: int = step_index
        self.tool_name: str = p.tool_name
        self.agent_id: str = p.agent_id
        self.framework: str = p.framework
        self.timestamp: datetime = p.timestamp
        self.input_payload: dict = p.input_payload
        self.output_payload: Optional[dict] = ctx.output_payload
        self.status: str = ctx.status
        self.latency_ms: float = ctx.latency_ms
        self.permission_scope: str = p.permission_scope
        self.parent_receipt_id: Optional[str] = p.parent_receipt_id
        self.children_receipt_ids: list = []

        # Enrichment fields (filled async by enrichment workers)
        self.drift_score: Optional[float] = None
        self.confidence_score: Optional[float] = None
        self.anomaly_flags: list = []
        self.failure_types: list = []
        self.node_status: str = "pending"
        self.cache_hit: bool = False
        self.staleness_flag: bool = False
        self.causal_contribution: Optional[float] = None
        self.enrichment_complete: bool = False

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class ReceiptFactory:
    """
    Stateful per-run factory. Maintains the chain hash and step counter.
    Thread-safe for sequential per-run use.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._step = 0
        self._prev_chain_hash = sha256(run_id)   # Genesis hash seeded from run_id

    def build(self, ctx: InterceptContext) -> ExecutionReceipt:
        receipt = ExecutionReceipt(ctx, self._prev_chain_hash, self._step)
        self._prev_chain_hash = receipt.chain_hash
        self._step += 1
        return receipt

    def verify_chain(self, receipts: list) -> bool:
        """
        Replay the chain hashes from scratch.
        Any mismatch means tampering has occurred.
        """
        prev = sha256(self.run_id)
        for r in receipts:
            components = {
                "receipt_id": r["receipt_id"],
                "run_id": r["run_id"],
                "step_index": r["step_index"],
                "tool_name": r["tool_name"],
                "agent_id": r["agent_id"],
                "timestamp": r["timestamp"].isoformat() if hasattr(r["timestamp"], "isoformat") else r["timestamp"],
                "input_hash": r["input_hash"],
                "output_hash": r.get("output_hash") or "",
                "status": r["status"],
                "prev_chain_hash": prev,
            }
            expected = sha256(_serialise(components))
            if expected != r["chain_hash"]:
                return False
            prev = r["chain_hash"]
        return True
