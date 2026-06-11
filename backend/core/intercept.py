"""
InterceptPoint — Universal interface for all framework adapters.
Every tool call normalises into this before hitting the Receipt Factory.
"""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


@dataclass
class InterceptPoint:
    """Universal interface captured for every tool invocation."""
    tool_name: str
    agent_id: str
    run_id: str
    input_payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    intercept_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    framework: str = "unknown"
    permission_scope: str = "read"
    parent_receipt_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InterceptContext:
    """Holds the full request-response context during tool execution."""
    point: InterceptPoint
    start_time_ns: int = field(default_factory=time.time_ns)
    output_payload: Optional[Dict[str, Any]] = None
    error: Optional[Exception] = None
    end_time_ns: Optional[int] = None
    status: str = "pending"   # success | timeout | error | ghost

    @property
    def latency_ms(self) -> float:
        if self.end_time_ns is None:
            return 0.0
        return (self.end_time_ns - self.start_time_ns) / 1_000_000


def _serialise(obj: Any) -> str:
    """Deterministic JSON serialisation (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class InterceptRouter:
    """
    Transparent proxy that wraps tool execution.
    Captures full request/response context regardless of outcome.
    """

    def __init__(self, receipt_factory, ghost_monitor):
        self.receipt_factory = receipt_factory
        self.ghost_monitor = ghost_monitor

    async def route(
        self,
        point: InterceptPoint,
        tool_fn: Callable,
        *args,
        **kwargs,
    ) -> InterceptContext:
        ctx = InterceptContext(point=point)
        self.ghost_monitor.register_expected(point.run_id, point.tool_name, point.intercept_id)

        try:
            result = await tool_fn(*args, **kwargs)
            ctx.output_payload = result if isinstance(result, dict) else {"result": result}
            ctx.status = "success"
        except TimeoutError as e:
            ctx.error = e
            ctx.status = "timeout"
        except Exception as e:
            ctx.error = e
            ctx.output_payload = {"error": str(e), "type": type(e).__name__}
            ctx.status = "error"
        finally:
            ctx.end_time_ns = time.time_ns()
            self.ghost_monitor.register_fired(point.run_id, point.tool_name, point.intercept_id)

        return ctx
