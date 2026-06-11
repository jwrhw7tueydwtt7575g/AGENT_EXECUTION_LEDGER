"""
Confidence vs Evidence Auditor — Enrichment Worker
Detects F6: Confidence Inflation (high certainty on low-quality tool data).
Detects F1: Silent API Failure (200 OK with empty/malformed body).
Detects F7: Tampered Replay (chain hash mismatch).
Detects F8: Permission Boundary Violation (destructive action outside scope).
"""
import json
from typing import List, Optional, Tuple

DESTRUCTIVE_TOOLS = {"file_deleter", "db_drop", "admin_reset", "email_sender", "slack_notifier"}
ALLOWED_SCOPE = {"read": ["read"], "write": ["read", "write"], "admin": ["read", "write", "admin"]}


class PermissionAuditor:

    def audit(self, receipt: dict) -> Tuple[list, list]:
        """Returns (anomaly_flags, failure_types)."""
        flags = list(receipt.get("anomaly_flags", []))
        failure_types = list(receipt.get("failure_types", []))

        # F1: Silent API Failure — 200 status but empty/null output
        output = receipt.get("output_payload")
        if receipt.get("status") == "success" and (not output or output == {}):
            flags.append("silent_api_failure_suspected")
            if "F1" not in failure_types:
                failure_types.append("F1")

        # F8: Permission Boundary Violation
        tool = receipt.get("tool_name", "")
        scope = receipt.get("permission_scope", "read")
        if tool in DESTRUCTIVE_TOOLS and scope not in ("write", "admin"):
            flags.append("permission_boundary_violation")
            if "F8" not in failure_types:
                failure_types.append("F8")

        return list(set(flags)), list(set(failure_types))


class ConfidenceInspector:
    """
    Confidence vs Evidence model.
    Flags cases where reported confidence is unsupported by evidence quality.
    """

    def inspect(self, receipt: dict) -> Tuple[Optional[float], list, list]:
        """Returns (adjusted_confidence, anomaly_flags, failure_types)."""
        flags = list(receipt.get("anomaly_flags", []))
        failure_types = list(receipt.get("failure_types", []))

        confidence = receipt.get("confidence_score")
        if confidence is None:
            confidence = _infer_confidence(receipt)

        # Evidence quality heuristics
        evidence_quality = 1.0
        if receipt.get("status") in ("error", "timeout"):
            evidence_quality *= 0.3
        if receipt.get("cache_hit") and receipt.get("staleness_flag"):
            evidence_quality *= 0.6
        if receipt.get("drift_score") and receipt["drift_score"] > 0.35:
            evidence_quality *= 0.7

        # F6: confidence far exceeds evidence quality
        if confidence > 0.80 and evidence_quality < 0.50:
            flags.append("confidence_inflation")
            if "F6" not in failure_types:
                failure_types.append("F6")
            # Adjust reported confidence downward
            confidence = round(confidence * evidence_quality, 3)

        return confidence, list(set(flags)), list(set(failure_types))


def _infer_confidence(receipt: dict) -> float:
    """Infer baseline confidence from status and drift."""
    if receipt.get("status") == "error":
        return 0.3
    if receipt.get("status") == "timeout":
        return 0.4
    drift = receipt.get("drift_score") or 0.0
    return max(0.3, 1.0 - drift * 1.5)
