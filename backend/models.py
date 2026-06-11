from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from enum import Enum
from datetime import datetime


class NodeStatus(str, Enum):
    verified = "verified"
    minor_issue = "minor_issue"
    significant_issue = "significant_issue"
    critical = "critical"
    ghost = "ghost"
    pending = "pending"


class FailureType(str, Enum):
    F1 = "F1"  # Silent API Failure
    F2 = "F2"  # Timeout Hallucination
    F3 = "F3"  # Ghost Tool Call
    F4 = "F4"  # Stale Cache Drift
    F5 = "F5"  # Multi-Agent Semantic Drift
    F6 = "F6"  # Confidence Inflation
    F7 = "F7"  # Tampered Replay
    F8 = "F8"  # Permission Boundary Violation


class ToolCallReceipt(BaseModel):
    receipt_id: str
    run_id: str
    step_index: int
    tool_name: str
    agent_id: str
    timestamp: datetime
    input_payload: Dict[str, Any]
    output_payload: Optional[Dict[str, Any]] = None
    input_hash: str
    output_hash: Optional[str] = None
    chain_hash: str
    status: str  # success, timeout, error, ghost
    node_status: NodeStatus = NodeStatus.pending
    drift_score: Optional[float] = None
    confidence_score: Optional[float] = None
    latency_ms: Optional[float] = None
    cache_hit: bool = False
    staleness_flag: bool = False
    anomaly_flags: List[str] = []
    failure_types: List[FailureType] = []
    parent_receipt_id: Optional[str] = None
    children_receipt_ids: List[str] = []
    permission_scope: Optional[str] = None
    enrichment_complete: bool = False


class RunSummary(BaseModel):
    run_id: str
    agent_name: str
    framework: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_steps: int = 0
    total_receipts: int = 0
    avg_drift: Optional[float] = None
    max_drift: Optional[float] = None
    chain_verified: bool = False
    ghost_calls: int = 0
    anomaly_count: int = 0
    trust_score: Optional[float] = None
    run_status: str = "running"  # running, completed, failed
    failure_summary: Dict[str, int] = {}


class DriftPoint(BaseModel):
    step_index: int
    receipt_id: str
    tool_name: str
    drift_score: float
    timestamp: datetime
    node_status: NodeStatus


class AnomalyEntry(BaseModel):
    run_id: str
    receipt_id: str
    tool_name: str
    anomaly_type: str
    severity: str
    timestamp: datetime
    details: Dict[str, Any] = {}


class RunComparisonRequest(BaseModel):
    run_id_a: str
    run_id_b: str
