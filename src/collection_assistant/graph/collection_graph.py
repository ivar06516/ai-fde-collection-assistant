"""LangGraph collection pipeline - 3-stage parallel/sequential workflow."""
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
    """Stage 1: Customer Profile + Account Profile in parallel."""
    import copy
    state_c = copy.deepcopy(state)
    state_a = copy.deepcopy(state)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fut_c = ex.submit(run_customer_profile_agent, state_c)
        fut_a = ex.submit(run_account_profile_agent, state_a)
        res_c = fut_c.result()
        res_a = fut_a.result()
    state["customer_profile"] = res_c["customer_profile"]
    state["account_profile"] = res_a["account_profile"]
    state["agent_statuses"]["customer_profile"] = res_c["agent_statuses"]["customer_profile"]
    state["agent_statuses"]["account_profile"] = res_a["agent_statuses"]["account_profile"]
    state["error_log"] += res_c.get("error_log", []) + res_a.get("error_log", [])
    return state


def _node_stage2(state: CollectionWorkflowState) -> CollectionWorkflowState:
    """Stage 2: Arrears Prediction + Dispute in parallel."""
    import copy
    state_arr = copy.deepcopy(state)
    state_dis = copy.deepcopy(state)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fut_arr = ex.submit(run_arrears_prediction_agent, state_arr)
        fut_dis = ex.submit(run_dispute_agent, state_dis)
        res_arr = fut_arr.result()
        res_dis = fut_dis.result()
    state["arrears_prediction"] = res_arr["arrears_prediction"]
    state["dispute_summary"] = res_dis["dispute_summary"]
    state["agent_statuses"]["arrears_prediction"] = res_arr["agent_statuses"]["arrears_prediction"]
    state["agent_statuses"]["dispute"] = res_dis["agent_statuses"]["dispute"]
    state["error_log"] += res_arr.get("error_log", []) + res_dis.get("error_log", [])
    return state


def _node_nba(state: CollectionWorkflowState) -> CollectionWorkflowState:
    return run_nba_agent(state)


def _node_audit(state: CollectionWorkflowState) -> CollectionWorkflowState:
    started = datetime.fromisoformat(state["started_at"])
    state["total_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    state["workflow_status"] = "completed"
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


def run_collection_pipeline(
    workflow_id: str, customer_id: str, account_id: str, trigger_context: str
) -> CollectionWorkflowState:
    """Synchronous entry point - runs the full pipeline and returns final state."""
    app = build_collection_graph()
    initial_state = _make_initial_state(workflow_id, customer_id, account_id, trigger_context)
    return app.invoke(initial_state)
