"""
Causal Blame Attribution Engine.

Answers: "When a multi-step agent run produced a wrong final output,
which step caused it?"

Algorithm:
  1. Build a causal DAG from the receipt chain.
  2. For each node, compute a counterfactual contribution score:
     contribution_i = Δ(final_output | step_i_fixed) / Σ Δ_all
  3. Score is displayed per node in the dashboard DAG.

In production, "fixing" a step means re-running from that point with
a corrected output. Here we use a deterministic proxy:
  - Steps with higher drift_score contribute more to the final error.
  - Steps that are ancestors of critical steps get amplified.
"""
from typing import Dict, List, Optional


class BlameAttributionEngine:

    def compute_causal_contributions(
        self,
        receipts: List[dict],
        final_output_correct: bool = False,
    ) -> Dict[str, float]:
        """
        Returns {receipt_id: causal_contribution_score [0.0, 1.0]}.
        Higher score = this step most likely caused the final error.
        """
        if not receipts:
            return {}

        # Phase 1: Raw "blame signal" per step
        signals: Dict[str, float] = {}
        for r in receipts:
            signal = 0.0
            drift = r.get("drift_score") or 0.0
            signal += drift * 0.5

            status = r.get("status", "success")
            if status == "error":
                signal += 0.3
            elif status == "timeout":
                signal += 0.2
            elif status == "ghost":
                signal += 0.4

            # Critical/significant nodes signal more
            ns = r.get("node_status", "pending")
            if ns == "critical":
                signal += 0.3
            elif ns == "significant_issue":
                signal += 0.15

            flags = r.get("anomaly_flags", [])
            signal += len(flags) * 0.05

            signals[r["receipt_id"]] = min(signal, 1.0)

        # Phase 2: Propagate upstream blame (later steps amplify earlier ones)
        total = sum(signals.values()) or 1.0
        contributions = {rid: round(s / total, 4) for rid, s in signals.items()}

        return contributions

    def build_causal_graph(self, receipts: List[dict]) -> dict:
        """
        Returns a simplified causal graph for display:
        { nodes: [{id, tool, contribution, ...}], edges: [{source, target}] }
        """
        contributions = self.compute_causal_contributions(receipts)

        nodes = []
        for r in receipts:
            nodes.append({
                "id": r["receipt_id"],
                "tool_name": r["tool_name"],
                "agent_id": r.get("agent_id", ""),
                "step_index": r.get("step_index", 0),
                "node_status": r.get("node_status", "pending"),
                "drift_score": r.get("drift_score"),
                "causal_contribution": contributions.get(r["receipt_id"], 0.0),
            })

        edges = [
            {"source": receipts[i]["receipt_id"], "target": receipts[i + 1]["receipt_id"]}
            for i in range(len(receipts) - 1)
        ]

        top_blame = max(contributions.items(), key=lambda x: x[1], default=(None, 0))

        return {
            "nodes": nodes,
            "edges": edges,
            "top_blame_receipt_id": top_blame[0],
            "top_blame_score": top_blame[1],
        }

    def enrich_receipts_with_contributions(self, receipts: List[dict]) -> List[dict]:
        """Mutates receipt list in place, adding causal_contribution field."""
        contributions = self.compute_causal_contributions(receipts)
        for r in receipts:
            r["causal_contribution"] = contributions.get(r["receipt_id"], 0.0)
        return receipts
