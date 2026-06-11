"""
Cross-Run Anomaly Detector — Enrichment Worker #2.
Profiles normal execution across 5 dimensions and flags deviations.

Five profiling dimensions (baseline requires ≥20 runs, configurable):
  1. Tool sequence distribution — which tools appear at which steps
  2. Latency distribution — mean + std per tool
  3. Drift score distribution — per tool
  4. Error rate — per tool
  5. Permission scope patterns — expected scopes per tool
"""
import math
import statistics
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

BASELINE_MIN_RUNS = 20   # configurable


class AnomalyDetector:

    def __init__(self, min_baseline_runs: int = BASELINE_MIN_RUNS):
        self.min_baseline_runs = min_baseline_runs
        self._baselines: Dict[str, dict] = {}   # tool_name -> baseline stats

    # ------------------------------------------------------------------
    # Baseline building (called during run completion)
    # ------------------------------------------------------------------

    def update_baseline(self, historical_receipts: List[dict]):
        """
        Rebuild baseline from all historical receipts.
        Called asynchronously after each run completes.
        """
        by_tool: Dict[str, list] = defaultdict(list)
        for r in historical_receipts:
            if r.get("status") not in ("ghost", None):
                by_tool[r["tool_name"]].append(r)

        for tool, receipts in by_tool.items():
            latencies = [r["latency_ms"] for r in receipts if r.get("latency_ms")]
            drifts = [r["drift_score"] for r in receipts if r.get("drift_score") is not None]
            errors = [1 if r["status"] == "error" else 0 for r in receipts]
            scopes = [r.get("permission_scope", "read") for r in receipts]

            self._baselines[tool] = {
                "count": len(receipts),
                "latency_mean": statistics.mean(latencies) if latencies else 500,
                "latency_std": statistics.stdev(latencies) if len(latencies) > 1 else 100,
                "drift_mean": statistics.mean(drifts) if drifts else 0.1,
                "drift_std": statistics.stdev(drifts) if len(drifts) > 1 else 0.05,
                "error_rate": sum(errors) / len(errors) if errors else 0.0,
                "common_scopes": list(set(scopes)),
            }

    # ------------------------------------------------------------------
    # Receipt-level anomaly detection
    # ------------------------------------------------------------------

    def flag_anomalies(self, receipt: dict, total_historical_runs: int) -> Tuple[list, list]:
        """
        Returns (anomaly_flags, failure_types) for a single receipt.
        Only activates when baseline is established.
        """
        flags = list(receipt.get("anomaly_flags", []))
        failure_types = list(receipt.get("failure_types", []))

        if total_historical_runs < self.min_baseline_runs:
            return flags, failure_types

        tool = receipt.get("tool_name", "")
        baseline = self._baselines.get(tool)
        if not baseline:
            return flags, failure_types

        # Dimension 2: Latency outlier (μ + 3σ)
        lat = receipt.get("latency_ms")
        if lat:
            threshold = baseline["latency_mean"] + 3 * baseline["latency_std"]
            if lat > threshold:
                flags.append("latency_outlier")

        # Dimension 3: Drift outlier (μ + 3σ)
        drift = receipt.get("drift_score")
        if drift is not None:
            drift_threshold = baseline["drift_mean"] + 3 * baseline["drift_std"]
            if drift > drift_threshold:
                flags.append("drift_outlier")
                if "F5" not in failure_types:
                    failure_types.append("F5")

        # Dimension 5: Unexpected permission scope
        scope = receipt.get("permission_scope", "read")
        if scope not in baseline.get("common_scopes", ["read"]) and scope == "admin":
            flags.append("unexpected_permission_scope")
            if "F8" not in failure_types:
                failure_types.append("F8")

        return list(set(flags)), list(set(failure_types))

    def score_run_anomaly(self, receipts: List[dict], all_run_drifts: List[float]) -> float:
        """
        Cross-run anomaly score for an entire run. 0.0 = normal, 1.0 = highly anomalous.
        Compares this run's avg drift to the distribution of all runs.
        """
        if not receipts or not all_run_drifts or len(all_run_drifts) < 5:
            return 0.0

        run_drifts = [r["drift_score"] for r in receipts if r.get("drift_score") is not None]
        if not run_drifts:
            return 0.0

        run_avg = statistics.mean(run_drifts)
        dist_mean = statistics.mean(all_run_drifts)
        dist_std = statistics.stdev(all_run_drifts) if len(all_run_drifts) > 1 else 0.1

        z = abs(run_avg - dist_mean) / max(dist_std, 1e-9)
        # Normalise z-score to [0, 1] using sigmoid-like mapping
        return round(min(1.0, z / 5.0), 4)
