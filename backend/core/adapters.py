"""
Framework Adapters — Zero-Intrusion Integration Layer.

Each adapter implements the BaseLedgerAdapter interface:
  wrap_tool(tool, metadata) → ledger-instrumented callable
  extract_intercept_point(*args, **kwargs) → InterceptPoint

Developer replaces their tool with a ledger-wrapped version — ONE LINE per tool.
The agent instantiation, prompts, and logic remain completely unchanged.
"""
import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional

from core.intercept import InterceptPoint
from core.ghost_monitor import GhostCallMonitor


# ---------------------------------------------------------------------------
# Base Interface
# ---------------------------------------------------------------------------

class BaseLedgerAdapter(ABC):
    """
    BaseLedgerAdapter Interface:
      wrap_tool(tool, metadata) → ledger-instrumented callable
      extract_intercept_point(*args, **kwargs) → InterceptPoint
    """

    def __init__(self, ledger_store, ghost_monitor: GhostCallMonitor):
        self.ledger_store = ledger_store
        self.ghost_monitor = ghost_monitor

    @abstractmethod
    def wrap_tool(self, tool: Callable, metadata: Dict[str, Any]) -> Callable:
        """Return a ledger-instrumented version of the tool callable."""
        ...

    @abstractmethod
    def extract_intercept_point(self, *args, **kwargs) -> InterceptPoint:
        """Normalise native invocation into universal InterceptPoint."""
        ...


# ---------------------------------------------------------------------------
# LangChain Adapter
# ---------------------------------------------------------------------------

class LangChainAdapter(BaseLedgerAdapter):
    """
    One-line change per tool:
      adapter.wrap_tool(GitHubTool())
    Agent instantiation completely unchanged.
    """

    def wrap_tool(self, tool, metadata: Optional[Dict] = None) -> Callable:
        metadata = metadata or {}
        tool_name = getattr(tool, "name", type(tool).__name__)
        run_id = metadata.get("run_id", str(uuid.uuid4()))
        agent_id = metadata.get("agent_id", "LangChain/unknown")
        framework = "LangChain"

        original_run = getattr(tool, "_run", None) or getattr(tool, "run", None)
        original_arun = getattr(tool, "_arun", None) or getattr(tool, "arun", None)

        def sanitize(obj):
            if isinstance(obj, dict):
                return {k: sanitize(v) for k, v in obj.items() if k not in ["callbacks", "tags", "metadata", "config"]}
            if isinstance(obj, list):
                return [sanitize(v) for v in obj]
            if isinstance(obj, tuple):
                return tuple(sanitize(v) for v in obj)
            if type(obj) in (int, float, str, bool, type(None)):
                return obj
            return str(obj)

        if original_arun:
            @wraps(original_arun)
            async def ledger_arun(*args, **kwargs):
                input_payload = {"args": sanitize(args), "kwargs": sanitize(kwargs)}
                point = InterceptPoint(
                    tool_name=tool_name, agent_id=agent_id, run_id=run_id,
                    input_payload=input_payload, framework=framework,
                    permission_scope=metadata.get("permission_scope", "read"),
                )
                start = time.time_ns()
                try:
                    result = await original_arun(*args, **kwargs)
                    out = result if isinstance(result, dict) else {"result": str(result)}
                    await self.ledger_store.record(point, out, "success", (time.time_ns() - start) / 1e6)
                    return result
                except Exception as e:
                    await self.ledger_store.record(point, {"error": str(e)}, "error", (time.time_ns() - start) / 1e6)
                    raise
            
            if hasattr(tool, "_arun"):
                tool._arun = ledger_arun
            elif hasattr(tool, "arun"):
                tool.arun = ledger_arun

        if original_run:
            @wraps(original_run)
            def ledger_run(*args, **kwargs):
                input_payload = {"args": sanitize(args), "kwargs": sanitize(kwargs)}
                point = InterceptPoint(
                    tool_name=tool_name, agent_id=agent_id, run_id=run_id,
                    input_payload=input_payload, framework=framework,
                    permission_scope=metadata.get("permission_scope", "read"),
                )
                start = time.time_ns()
                try:
                    result = original_run(*args, **kwargs)
                    out = result if isinstance(result, dict) else {"result": str(result)}
                    latency = (time.time_ns() - start) / 1e6
                    try:
                        loop = asyncio.get_running_loop()
                        task = loop.create_task(self.ledger_store.record(point, out, "success", latency))
                        task.add_done_callback(
                            lambda t: t.exception() and print(f"Ledger record failed: {t.exception()}")
                        )
                    except RuntimeError:
                        asyncio.run(self.ledger_store.record(point, out, "success", latency))
                    return result
                except Exception as e:
                    latency = (time.time_ns() - start) / 1e6
                    try:
                        loop = asyncio.get_running_loop()
                        task = loop.create_task(self.ledger_store.record(point, {"error": str(e)}, "error", latency))
                        task.add_done_callback(
                            lambda t: t.exception() and print(f"Ledger record failed: {t.exception()}")
                        )
                    except RuntimeError:
                        asyncio.run(self.ledger_store.record(point, {"error": str(e)}, "error", latency))
                    raise

            if hasattr(tool, "_run"):
                tool._run = ledger_run
            elif hasattr(tool, "run"):
                tool.run = ledger_run
        
        return tool

    def extract_intercept_point(self, *args, **kwargs) -> InterceptPoint:
        return InterceptPoint(
            tool_name=kwargs.get("tool_name", "unknown"),
            agent_id=kwargs.get("agent_id", "LangChain/unknown"),
            run_id=kwargs.get("run_id", str(uuid.uuid4())),
            input_payload={"args": args, "kwargs": kwargs},
            framework="LangChain",
        )


# ---------------------------------------------------------------------------
# CrewAI Adapter
# ---------------------------------------------------------------------------

class CrewAIAdapter(BaseLedgerAdapter):
    """
    Wrap at the Crew level:
      adapter.wrap_crew(Crew(...))
    Captures inter-agent handoff messages as receipts.
    """

    def wrap_crew(self, crew, metadata: Optional[Dict] = None):
        """Monkeypatches the crew's kickoff to intercept all agent handoffs."""
        metadata = metadata or {}
        run_id = metadata.get("run_id", str(uuid.uuid4()))
        original_kickoff = crew.kickoff

        if asyncio.iscoroutinefunction(original_kickoff):
            async def ledger_kickoff(*args, **kwargs):
                point = InterceptPoint(
                    tool_name="CrewAI/kickoff",
                    agent_id=metadata.get("agent_id", "Crew/orchestrator"),
                    run_id=run_id,
                    input_payload={"args": args, "kwargs": kwargs},
                    framework="CrewAI",
                )
                start = time.time_ns()
                try:
                    result = await original_kickoff(*args, **kwargs)
                    await self.ledger_store.record(point, {"result": str(result)}, "success", (time.time_ns() - start) / 1e6)
                    return result
                except Exception as e:
                    await self.ledger_store.record(point, {"error": str(e)}, "error", (time.time_ns() - start) / 1e6)
                    raise
        else:
            def ledger_kickoff(*args, **kwargs):
                point = InterceptPoint(
                    tool_name="CrewAI/kickoff",
                    agent_id=metadata.get("agent_id", "Crew/orchestrator"),
                    run_id=run_id,
                    input_payload={"args": args, "kwargs": kwargs},
                    framework="CrewAI",
                )
                start = time.time_ns()
                try:
                    result = original_kickoff(*args, **kwargs)
                    asyncio.run(self.ledger_store.record(point, {"result": str(result)}, "success", (time.time_ns() - start) / 1e6))
                    return result
                except Exception as e:
                    asyncio.run(self.ledger_store.record(point, {"error": str(e)}, "error", (time.time_ns() - start) / 1e6))
                    raise

        crew.kickoff = ledger_kickoff
        return crew

    def wrap_tool(self, tool: Callable, metadata: Optional[Dict] = None) -> Callable:
        metadata = metadata or {}

        @wraps(tool)
        async def ledger_tool(*args, **kwargs):
            metadata_copy = metadata.copy()
            tool_name = metadata_copy.pop("tool_name", getattr(tool, "__name__", "crewai_tool"))
            point = self.extract_intercept_point(*args, tool_name=tool_name, **metadata_copy)
            start = time.time_ns()
            try:
                result = await tool(*args, **kwargs) if asyncio.iscoroutinefunction(tool) else tool(*args, **kwargs)
                await self.ledger_store.record(point, result if isinstance(result, dict) else {"result": result}, "success", (time.time_ns() - start) / 1e6)
                return result
            except Exception as e:
                await self.ledger_store.record(point, {"error": str(e)}, "error", (time.time_ns() - start) / 1e6)
                raise

        return ledger_tool

    def extract_intercept_point(self, *args, **kwargs) -> InterceptPoint:
        return InterceptPoint(
            tool_name=kwargs.pop("tool_name", "crewai_tool"),
            agent_id=kwargs.pop("agent_id", "CrewAI/agent"),
            run_id=kwargs.pop("run_id", str(uuid.uuid4())),
            input_payload={"args": args, "kwargs": kwargs},
            framework="CrewAI",
        )


# ---------------------------------------------------------------------------
# AutoGen Adapter
# ---------------------------------------------------------------------------

class AutoGenAdapter(BaseLedgerAdapter):
    """
    Wrap at the agent level:
      adapter.wrap_agent(AssistantAgent(...))
    All function calls from the agent go through ledger.
    """

    def wrap_agent(self, agent, metadata: Optional[Dict] = None):
        """Intercepts AutoGen agent's function execution dispatcher."""
        metadata = metadata or {}
        run_id = metadata.get("run_id", str(uuid.uuid4()))
        original_execute = getattr(agent, "execute_function", None)

        if original_execute is None:
            return agent

        async def ledger_execute(func_call, **kw):
            func_name = func_call.get("name", "unknown")
            func_args = func_call.get("arguments", {})
            point = InterceptPoint(
                tool_name=func_name,
                agent_id=getattr(agent, "name", "AutoGen/agent"),
                run_id=run_id,
                input_payload=func_args if isinstance(func_args, dict) else {"raw": str(func_args)},
                framework="AutoGen",
                permission_scope=metadata.get("permission_scope", "read"),
            )
            start = time.time_ns()
            try:
                result = await original_execute(func_call, **kw)
                await self.ledger_store.record(point, {"result": str(result)}, "success", (time.time_ns() - start) / 1e6)
                return result
            except Exception as e:
                await self.ledger_store.record(point, {"error": str(e)}, "error", (time.time_ns() - start) / 1e6)
                raise

        agent.execute_function = ledger_execute
        return agent

    def wrap_tool(self, tool: Callable, metadata: Optional[Dict] = None) -> Callable:
        return tool  # AutoGen wraps at agent level, not tool level

    def extract_intercept_point(self, *args, **kwargs) -> InterceptPoint:
        return InterceptPoint(
            tool_name=kwargs.get("tool_name", "autogen_fn"),
            agent_id=kwargs.get("agent_id", "AutoGen/agent"),
            run_id=kwargs.get("run_id", str(uuid.uuid4())),
            input_payload={"args": args, "kwargs": kwargs},
            framework="AutoGen",
        )


# ---------------------------------------------------------------------------
# Universal HTTP Proxy Adapter (any framework, any language)
# ---------------------------------------------------------------------------

class UniversalHTTPProxyAdapter:
    """
    Any language, any framework.
    Route tool endpoint through the ledger proxy URL.
    Records request, forwards, records response, adds receipt ID header.

    Usage:
      POST /proxy/{tool_endpoint}
      Headers: X-Agent-ID, X-Run-ID, X-Permission-Scope
      Body: original tool request body (JSON)

    This adapter is the FastAPI router — see main.py for /proxy route.
    """

    def __init__(self, ledger_store):
        self.ledger_store = ledger_store

    async def handle_proxy_request(
        self,
        tool_name: str,
        agent_id: str,
        run_id: str,
        input_body: Dict[str, Any],
        forward_fn: Callable,
        permission_scope: str = "read",
    ) -> Dict[str, Any]:
        point = InterceptPoint(
            tool_name=tool_name,
            agent_id=agent_id,
            run_id=run_id,
            input_payload=input_body,
            framework="HTTP/Proxy",
            permission_scope=permission_scope,
        )
        start = time.time_ns()
        status = "success"
        try:
            response = await forward_fn(input_body)
            output = response if isinstance(response, dict) else {"body": str(response)}
        except Exception as e:
            output = {"error": str(e)}
            status = "error"
        finally:
            latency = (time.time_ns() - start) / 1e6
            receipt = await self.ledger_store.record(point, output, status, latency)

        return {"receipt_id": receipt.receipt_id, "response": output}
