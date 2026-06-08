"""Audit Agent — builds the decision audit trail and writes to DB."""
import json
from datetime import datetime, timezone

from collection_assistant.db.models import WorkflowAudit
from collection_assistant.db.session import db_session
from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant import event_bus
from collection_assistant.tools.audit_tools import build_audit_record


def run_audit_agent(state: CollectionWorkflowState) -> CollectionWorkflowState:
    started_at = datetime.now(timezone.utc)

    state["agent_statuses"]["audit"] = {
        "stage": 3, "status": "running",
        "started_at": started_at.isoformat(), "completed_at": None,
        "elapsed_ms": None, "error": None,
    }
    event_bus.emit(state["workflow_id"], "agent_update", {"agent": "audit", "stage": 3, "status": "running", "elapsed_ms": None, "error": None})

    try:
        workflow_id = state["workflow_id"]
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

        # AC-007-01/03: pass audit elapsed so it appears as the 6th lineage entry
        audit_data = build_audit_record(workflow_id, state, audit_elapsed_ms=elapsed_ms)  # type: ignore[arg-type]
        state["audit_record"] = audit_data

        nba = state.get("nba_recommendation") or {}
        # Include agent_statuses in full_state_json for elapsed_ms preservation
        record = WorkflowAudit(
            workflow_id=workflow_id,
            customer_id=state["customer_id"],
            account_id=state["account_id"],
            trigger_context=state.get("trigger_context", ""),
            nba_action=nba.get("action"),
            nba_channel=nba.get("channel"),
            nba_confidence=nba.get("confidence_score"),
            nba_rationale=nba.get("rationale"),
            full_state_json=json.dumps({
                k: v for k, v in state.items()
                if k != "agent_statuses"          # excluded to keep JSON compact
            }, default=str),
            status=state.get("workflow_status", "completed"),
            total_ms=state.get("total_ms"),
        )
        with db_session() as session:
            session.add(record)

        state["agent_statuses"]["audit"].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "audit", "stage": 3, "status": "completed", "elapsed_ms": elapsed_ms, "error": None})
    except Exception as e:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["agent_statuses"]["audit"].update({
            "status": "error", "error": str(e), "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "audit", "stage": 3, "status": "error", "elapsed_ms": elapsed_ms, "error": str(e)})
        state["error_log"].append(f"audit: {e}")

    return state


