"""LangGraph collection pipeline - 3-stage parallel/sequential workflow.

Performance fixes applied:
- Fix 1: deepcopy replaced with shallow split-and-merge (agents only write one output key)
- Fix 2: Module-level persistent ThreadPoolExecutor (no spawn/destroy per stage)
- Fix 3: _COMPILED_GRAPH singleton (already in place)
"""
import concurrent.futures
import time
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from collection_assistant.agents.account_profile import run_account_profile_agent
from collection_assistant.agents.arrears_prediction import run_arrears_prediction_agent
from collection_assistant.agents.audit import run_audit_agent
from collection_assistant.agents.customer_profile import run_customer_profile_agent
from collection_assistant.agents.dispute import run_dispute_agent
from collection_assistant.agents.nba import run_nba_agent
from collection_assistant.graph.state import AgentStatus, CollectionWorkflowState

# Fix 2: Persistent pool — avoid creating/destroying per stage
_STAGE_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent")


def _run_agent_with_span(
    agent_name: str,
    stage: int,
    fn,
    state: CollectionWorkflowState,
    parent_ctx=None,
) -> CollectionWorkflowState:
    """Wrap an agent call in an OTel span, record metrics and NR custom events.

    parent_ctx must be passed for threaded agents so the child span is correctly
    nested under the pipeline trace (OTel context is not inherited by threads).
    """
    from collection_assistant.observability import get_tracer, newrelic_helper as nr
    from collection_assistant.observability.metrics import record_agent_run, record_error

    tracer = get_tracer()
    t0 = time.monotonic()
    otel_token = None

    # Attach parent context in worker threads so spans nest properly
    if tracer and parent_ctx is not None:
        from opentelemetry import context as otel_ctx
        otel_token = otel_ctx.attach(parent_ctx)

    try:
        if tracer:
            with tracer.start_as_current_span(
                f"agent.{agent_name}",
                attributes={
                    "agent.name": agent_name,
                    "agent.stage": str(stage),
                    "workflow.id": state.get("workflow_id", ""),
                    "customer.id": state.get("customer_id", ""),
                },
            ) as span:
                result = fn(state)
                elapsed = time.monotonic() - t0
                elapsed_ms = int(elapsed * 1000)
                agent_st = (result.get("agent_statuses") or {}).get(agent_name) or {}
                success = agent_st.get("status") != "error"

                if not success:
                    err = agent_st.get("error", "")
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", err[:200])
                    span.add_event("agent.error", {"error.message": err[:200]})
                    nr.record_agent_error_event(agent_name, state.get("workflow_id", ""), err)
                    record_error(agent_name, "AgentError", state.get("trigger_context", ""))
                else:
                    span.add_event("agent.completed", {"duration_ms": str(elapsed_ms)})

                nr.record_agent_completed(
                    agent_name, state.get("workflow_id", ""), elapsed_ms, success
                )
                record_agent_run(agent_name, stage, elapsed)
                return result
        else:
            result = fn(state)
            elapsed = time.monotonic() - t0
            elapsed_ms = int(elapsed * 1000)
            agent_st = (result.get("agent_statuses") or {}).get(agent_name) or {}
            success = agent_st.get("status") != "error"
            if not success:
                nr.record_agent_error_event(
                    agent_name, state.get("workflow_id", ""), agent_st.get("error", "")
                )
                record_error(agent_name, "AgentError", state.get("trigger_context", ""))
            nr.record_agent_completed(agent_name, state.get("workflow_id", ""), elapsed_ms, success)
            record_agent_run(agent_name, stage, elapsed)
            return result
    finally:
        if otel_token is not None:
            from opentelemetry import context as otel_ctx
            otel_ctx.detach(otel_token)


def _make_initial_state(
    workflow_id: str, customer_id: str, account_id: str, trigger_context: str
) -> CollectionWorkflowState:
    now = datetime.now(timezone.utc).isoformat()
    stages = {
        "customer_profile": 1, "account_profile": 1,
        "arrears_prediction": 2, "dispute": 2, "nba": 3, "audit": 3,
    }
    statuses = {
        name: AgentStatus(
            stage=stage, status="waiting",
            started_at=None, completed_at=None, elapsed_ms=None, error=None,
        )
        for name, stage in stages.items()
    }
    return CollectionWorkflowState(
        workflow_id=workflow_id,
        customer_id=customer_id,
        account_id=account_id,
        trigger_context=trigger_context,
        agent_statuses=statuses,
        customer_profile=None,
        account_profile=None,
        arrears_prediction=None,
        dispute_summary=None,
        nba_recommendation=None,
        audit_record=None,
        workflow_status="in_progress",
        error_log=[],
        started_at=now,
        completed_at=None,
        total_ms=None,
    )


def _node_stage1(state: CollectionWorkflowState) -> CollectionWorkflowState:
    """Stage 1: Customer Profile + Account Profile in parallel.

    Fix 1: No deepcopy. Each agent reads its own input keys (customer_id, account_id)
    from the shared state (read-only at this point) and writes back one output key.
    The state dict is the shared object; agents only mutate their own output key +
    agent_statuses sub-key. Since both agents write DIFFERENT keys there is no race.
    error_log append is protected by GIL for list.append in CPython.
    """
    from opentelemetry import context as otel_ctx
    parent_ctx = otel_ctx.get_current()
    fut_c = _STAGE_POOL.submit(_run_agent_with_span, "customer_profile", 1, run_customer_profile_agent, state, parent_ctx)
    fut_a = _STAGE_POOL.submit(_run_agent_with_span, "account_profile", 1, run_account_profile_agent, state, parent_ctx)
    fut_c.result()
    fut_a.result()
    return state


def _node_stage2(state: CollectionWorkflowState) -> CollectionWorkflowState:
    """Stage 2: Arrears Prediction + Dispute in parallel.

    Fix 1: No deepcopy. Both agents read customer_profile + account_profile (read-only)
    and write their own distinct output keys. No write-write conflict.
    """
    from opentelemetry import context as otel_ctx
    parent_ctx = otel_ctx.get_current()
    fut_arr = _STAGE_POOL.submit(_run_agent_with_span, "arrears_prediction", 2, run_arrears_prediction_agent, state, parent_ctx)
    fut_dis = _STAGE_POOL.submit(_run_agent_with_span, "dispute", 2, run_dispute_agent, state, parent_ctx)
    fut_arr.result()
    fut_dis.result()
    return state


def _node_nba(state: CollectionWorkflowState) -> CollectionWorkflowState:
    return _run_agent_with_span("nba", 3, run_nba_agent, state)


def _node_audit(state: CollectionWorkflowState) -> CollectionWorkflowState:
    started = datetime.fromisoformat(state["started_at"])
    state["total_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    state["workflow_status"] = "error" if state.get("error_log") else "completed"
    state = _run_agent_with_span("audit", 3, run_audit_agent, state)
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    return state


def build_collection_graph() -> Any:
    graph = StateGraph(CollectionWorkflowState)
    graph.add_node("stage1", _node_stage1)
    graph.add_node("stage2", _node_stage2)
    graph.add_node("nba", _node_nba)
    graph.add_node("audit", _node_audit)
    graph.add_edge(START, "stage1")
    graph.add_edge("stage1", "stage2")
    graph.add_edge("stage2", "nba")
    graph.add_edge("nba", "audit")
    graph.add_edge("audit", END)
    return graph.compile()


_COMPILED_GRAPH = None  # Fix 3: compile once, reuse


def run_collection_pipeline(
    workflow_id: str, customer_id: str, account_id: str, trigger_context: str
) -> CollectionWorkflowState:
    """Synchronous entry point — wraps the full pipeline in an OTel parent span."""
    from collection_assistant.observability import get_tracer, newrelic_helper as nr
    from collection_assistant.observability.metrics import record_workflow_start, record_workflow_end

    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_collection_graph()
    initial_state = _make_initial_state(workflow_id, customer_id, account_id, trigger_context)

    tracer = get_tracer()
    t0 = record_workflow_start(trigger_context)

    span_attrs = {
        "workflow.id": workflow_id,
        "customer.id": customer_id,
        "account.id": account_id,
        "trigger.context": trigger_context,
    }

    if tracer:
        with tracer.start_as_current_span("pipeline.collection_workflow", attributes=span_attrs) as span:
            try:
                result = _COMPILED_GRAPH.invoke(initial_state)
            except Exception as e:
                from opentelemetry.trace import StatusCode
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                record_workflow_end(t0, "error", trigger_context)
                nr.notice_error(e, {"workflow.id": workflow_id, "customer.id": customer_id})
                raise

            return _record_pipeline_completion(result, span, t0, trigger_context, workflow_id, nr,
                                               record_workflow_end)
    else:
        try:
            result = _COMPILED_GRAPH.invoke(initial_state)
        except Exception:
            record_workflow_end(t0, "error", trigger_context)
            raise
        return _record_pipeline_completion(result, None, t0, trigger_context, workflow_id, nr,
                                           record_workflow_end)


def _record_pipeline_completion(result, span, t0, trigger_context, workflow_id, nr, record_end):
    """Extract final state attributes and record workflow + NR metrics."""
    status = result.get("workflow_status", "completed")
    nba = (result.get("nba_recommendation") or {}).get("action") or ""
    hold = bool((result.get("dispute_summary") or {}).get("collection_hold", False))
    error_count = len(result.get("error_log") or [])
    elapsed_ms = result.get("total_ms") or int(time.monotonic() * 1000)

    # Identify slowest agent (bottleneck)
    bottleneck = max(
        ((n, (s or {}).get("elapsed_ms") or 0) for n, s in (result.get("agent_statuses") or {}).items()),
        key=lambda x: x[1],
        default=("unknown", 0),
    )[0]

    if span is not None:
        span.set_attribute("workflow.status", status)
        span.set_attribute("nba.action", nba)
        span.set_attribute("error.count", error_count)
        span.set_attribute("bottleneck.agent", bottleneck)
        if error_count > 0:
            span.set_attribute("error", True)

    record_end(t0, status, trigger_context, nba or None, hold)
    nr.record_pipeline_metrics(
        workflow_id, elapsed_ms, trigger_context,
        nba_action=nba or None,
        bottleneck_agent=bottleneck,
        stages_completed=4,
        error_count=error_count,
    )
    return result
