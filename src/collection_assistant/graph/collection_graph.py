"""LangGraph collection pipeline - 3-stage parallel/sequential workflow.

Performance fixes applied:
- Fix 1: deepcopy replaced with shallow split-and-merge (agents only write one output key)
- Fix 2: Module-level persistent ThreadPoolExecutor (no spawn/destroy per stage)
- Fix 3: _COMPILED_GRAPH singleton (already in place)
"""
import concurrent.futures
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
    fut_c = _STAGE_POOL.submit(run_customer_profile_agent, state)
    fut_a = _STAGE_POOL.submit(run_account_profile_agent, state)
    fut_c.result()
    fut_a.result()
    # futures block until done — agents update state in place and return self
    # Just ensure error_log merged (agents already wrote to state directly)
    return state


def _node_stage2(state: CollectionWorkflowState) -> CollectionWorkflowState:
    """Stage 2: Arrears Prediction + Dispute in parallel.

    Fix 1: No deepcopy. Both agents read customer_profile + account_profile (read-only)
    and write their own distinct output keys. No write-write conflict.
    """
    fut_arr = _STAGE_POOL.submit(run_arrears_prediction_agent, state)
    fut_dis = _STAGE_POOL.submit(run_dispute_agent, state)
    fut_arr.result()
    fut_dis.result()
    return state


def _node_nba(state: CollectionWorkflowState) -> CollectionWorkflowState:
    return run_nba_agent(state)


def _node_audit(state: CollectionWorkflowState) -> CollectionWorkflowState:
    started = datetime.fromisoformat(state["started_at"])
    state["total_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    state["workflow_status"] = "error" if state.get("error_log") else "completed"
    state = run_audit_agent(state)
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
    """Synchronous entry point - runs the full pipeline and returns final state."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_collection_graph()
    initial_state = _make_initial_state(workflow_id, customer_id, account_id, trigger_context)
    return _COMPILED_GRAPH.invoke(initial_state)
