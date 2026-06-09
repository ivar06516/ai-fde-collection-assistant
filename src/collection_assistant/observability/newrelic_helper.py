"""New Relic observability helper — custom events, metrics, and error tracking.

Provides a clean API that mirrors newrelic.agent conventions but uses
OpenTelemetry (OTLP) internally, which is the recommended approach for
vendor-agnostic observability.

All functions are safe no-ops when OTel is not configured.

New Relic NRQL queries for custom events (span events via OTLP):
  SELECT * FROM SpanEvent WHERE name = 'AgentCompleted' SINCE 1 hour ago
  SELECT average(numeric(duration_ms)) FROM SpanEvent WHERE name = 'AgentCompleted'
    FACET agent_name SINCE 1 hour ago TIMESERIES
  SELECT count(*) FROM SpanEvent WHERE name = 'AgentError'
    FACET agent_name SINCE 1 hour ago
  SELECT * FROM SpanEvent WHERE name = 'PipelineMetrics' SINCE 30 minutes ago
"""
import logging
import time
from typing import Any, Optional

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _current_span():
    """Return the active OTel span, or a no-op span if OTel unavailable."""
    try:
        from opentelemetry import trace
        return trace.get_current_span()
    except ImportError:
        return None


def add_custom_attribute(key: str, value: Any) -> None:
    """Add a key-value attribute to the current active span."""
    span = _current_span()
    if span:
        try:
            span.set_attribute(key, str(value) if not isinstance(value, (bool, int, float, str)) else value)
        except Exception:
            pass


def notice_error(exc: Exception, attributes: Optional[dict] = None) -> None:
    """Record an exception on the current span with full context.

    Equivalent to newrelic.agent.notice_error().
    Sets span status to ERROR and records the exception stacktrace.
    """
    span = _current_span()
    if not span:
        return
    try:
        from opentelemetry.trace import StatusCode
        span.record_exception(exc, attributes={k: str(v) for k, v in (attributes or {}).items()})
        span.set_status(StatusCode.ERROR, str(exc))
    except Exception:
        pass


def record_custom_event(event_type: str, attributes: dict) -> None:
    """Add a named span event — appears in New Relic as SpanEvent.

    Equivalent to newrelic.agent.record_custom_event().
    Also emits a structured log line for NR Logs correlation.

    Query in New Relic:
      SELECT * FROM SpanEvent WHERE name = '<event_type>' SINCE 1 hour ago
    """
    span = _current_span()
    safe_attrs = {k: str(v) for k, v in attributes.items()}
    if span:
        try:
            span.add_event(event_type, attributes=safe_attrs)
        except Exception:
            pass
    # Emit as structured log so the event also appears in NR Logs
    _log.info(event_type, extra={"nr_event_type": event_type, **safe_attrs})


# ---------------------------------------------------------------------------
# Agent lifecycle events
# ---------------------------------------------------------------------------

def record_agent_started(
    agent_name: str,
    workflow_id: str,
    stage: int,
    trigger_context: str,
) -> float:
    """Record agent start. Returns monotonic timestamp for duration calculation."""
    record_custom_event("AgentStarted", {
        "agent_name": agent_name,
        "workflow_id": workflow_id,
        "stage": stage,
        "trigger_context": trigger_context,
        "timestamp": time.time(),
    })
    return time.monotonic()


def record_agent_completed(
    agent_name: str,
    workflow_id: str,
    duration_ms: int,
    success: bool,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Record agent completion event.

    NRQL:
      SELECT average(numeric(duration_ms)) FROM SpanEvent
      WHERE name = 'AgentCompleted' FACET agent_name SINCE 1 hour ago TIMESERIES
    """
    record_custom_event("AgentCompleted", {
        "agent_name": agent_name,
        "workflow_id": workflow_id,
        "duration_ms": duration_ms,
        "success": success,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    })


def record_llm_call(
    agent_name: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
) -> None:
    """Record an LLM API call for cost and latency tracking.

    NRQL:
      SELECT sum(numeric(prompt_tokens)), sum(numeric(completion_tokens))
      FROM SpanEvent WHERE name = 'LLMCall' FACET model SINCE 1 day ago
    """
    record_custom_event("LLMCall", {
        "agent_name": agent_name,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "latency_ms": latency_ms,
    })


def record_agent_error_event(
    agent_name: str,
    workflow_id: str,
    error_message: str,
    error_type: str = "AgentError",
    retry_count: int = 0,
) -> None:
    """Record an agent error with full context.

    NRQL:
      SELECT count(*) FROM SpanEvent WHERE name = 'AgentError'
      FACET agent_name, error_type SINCE 1 hour ago
    """
    record_custom_event("AgentError", {
        "agent_name": agent_name,
        "workflow_id": workflow_id,
        "error_type": error_type,
        "error_message": error_message[:500],
        "retry_count": retry_count,
    })


# ---------------------------------------------------------------------------
# Pipeline-level events
# ---------------------------------------------------------------------------

def record_pipeline_metrics(
    workflow_id: str,
    total_duration_ms: int,
    trigger_context: str,
    nba_action: Optional[str] = None,
    bottleneck_agent: Optional[str] = None,
    stages_completed: int = 4,
    error_count: int = 0,
) -> None:
    """Record end-to-end pipeline performance metrics.

    NRQL:
      SELECT average(numeric(total_duration_ms)) FROM SpanEvent
      WHERE name = 'PipelineMetrics' FACET trigger_context SINCE 30 minutes ago

      SELECT count(*) FROM SpanEvent WHERE name = 'PipelineMetrics'
      FACET bottleneck_agent SINCE 1 hour ago
    """
    record_custom_event("PipelineMetrics", {
        "workflow_id": workflow_id,
        "total_duration_ms": total_duration_ms,
        "trigger_context": trigger_context,
        "nba_action": nba_action or "unknown",
        "bottleneck_agent": bottleneck_agent or "unknown",
        "stages_completed": stages_completed,
        "error_count": error_count,
        "success": error_count == 0,
    })


def record_user_action(
    action: str,
    customer_id: str,
    workflow_id: str,
    result: str,
) -> None:
    """Record a user-initiated business action.

    NRQL:
      SELECT count(*) FROM SpanEvent WHERE name = 'UserAction'
      FACET action SINCE 1 hour ago
    """
    record_custom_event("UserAction", {
        "action": action,
        "customer_id": customer_id,
        "workflow_id": workflow_id,
        "result": result,
        "timestamp": time.time(),
    })
