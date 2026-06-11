"""
Semantic Drift Engine — Enrichment Worker #1
Uses SentenceTransformer ('all-MiniLM-L6-v2') to embed tool outputs
and agent interpretations, then computes real cosine distance.

Model is loaded once at module level (singleton) and reused across calls.
Falls back to hash-distance if sentence-transformers fails to initialise.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---- Embedding Model (singleton, loaded once) ----
_model = None
_use_real_embeddings = True

def _get_model():
    global _model, _use_real_embeddings
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("SemanticDriftEngine: loaded SentenceTransformer all-MiniLM-L6-v2")
    except Exception as e:
        logger.warning(f"SentenceTransformer unavailable ({e}), using hash-distance fallback")
        _use_real_embeddings = False
        _model = None
    return _model


# ---- Fallback: deterministic hash-distance ----
import hashlib, math, random

def _hash_vector(text: str, dim: int = 128) -> list:
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else [0.0] * dim

def _cosine_hash(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return 1.0 - min(1.0, max(0.0, dot))


# ---- Core drift computation ----

def _compute_cosine_distance(text_a: str, text_b: str) -> float:
    model = _get_model()
    if model is not None and _use_real_embeddings:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            embeddings = model.encode([text_a, text_b], convert_to_numpy=True)
            sim = cosine_similarity(embeddings[0:1], embeddings[1:2])[0][0]
            return round(float(1.0 - sim), 4)
        except Exception as e:
            logger.warning(f"Embedding computation failed ({e}), using hash fallback")

    # Fallback
    return round(_cosine_hash(_hash_vector(text_a), _hash_vector(text_b)), 4)


class SemanticDriftEngine:
    """
    Async-safe enrichment worker.
    Called after receipt creation — never blocks the agent.
    """

    def compute_drift(
        self,
        raw_output: str,
        agent_interpretation: Optional[str],
        tool_name: str = "",
    ) -> float:
        """
        Returns cosine distance in [0.0, 1.0]:
          0.0 → identical semantic meaning
          1.0 → completely divergent
        """
        if not raw_output:
            raw_output = f"{tool_name}_output"
        if not agent_interpretation:
            # No interpretation registered — simulate partial drift
            agent_interpretation = tool_name or "unknown_interpretation"

        return _compute_cosine_distance(raw_output, agent_interpretation)

    def determine_node_status(
        self,
        drift: Optional[float],
        latency_ms: float,
        run_latency_mean: float,
        run_latency_std: float,
        anomaly_flags: list,
        status: str,
    ) -> str:
        """
        DAG node colour schema:
          🟢 verified       — drift < 0.15, no anomaly
          🟡 minor_issue    — drift 0.15–0.35 OR latency > μ+2σ
          🟠 significant    — drift 0.35–0.60 OR anomaly flag
          🔴 critical       — drift > 0.60 OR hash_mismatch
          ⚫ ghost          — never fired
          ⚪ pending        — enrichment not complete
        """
        if status == "ghost":
            return "ghost"
        if drift is None:
            return "pending"

        latency_threshold = run_latency_mean + 2 * run_latency_std

        if drift > 0.60 or "hash_mismatch" in anomaly_flags:
            return "critical"
        if drift > 0.35 or len(anomaly_flags) > 0:
            return "significant_issue"
        if drift > 0.15 or latency_ms > latency_threshold:
            return "minor_issue"
        return "verified"

    def enrich_receipt(self, receipt: dict, agent_interpretation: Optional[str] = None) -> dict:
        """
        In-place enrichment of a receipt dict.
        Computes semantic drift, flags F4/F6 anomalies, marks enrichment complete.
        """
        raw = ""
        if receipt.get("output_payload"):
            raw = str(receipt["output_payload"])
        elif receipt.get("status"):
            raw = receipt["status"]

        drift = self.compute_drift(raw, agent_interpretation, receipt.get("tool_name", ""))
        receipt["drift_score"] = drift

        # Confidence inflation check (F6)
        confidence = receipt.get("confidence_score") or 0.75
        flags = list(receipt.get("anomaly_flags", []))
        failure_types = list(receipt.get("failure_types", []))

        if confidence > 0.88 and drift > 0.30:
            if "confidence_inflation" not in flags:
                flags.append("confidence_inflation")
            if "F6" not in failure_types:
                failure_types.append("F6")

        # Stale cache (F4)
        if receipt.get("staleness_flag") and "F4" not in failure_types:
            failure_types.append("F4")

        receipt["anomaly_flags"] = flags
        receipt["failure_types"] = failure_types
        receipt["enrichment_complete"] = True
        return receipt
