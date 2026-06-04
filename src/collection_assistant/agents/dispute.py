"""Dispute Agent — identifies open disputes and collection holds."""
import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from collection_assistant.config import get_settings
from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant import event_bus
from collection_assistant.llm.client_factory import get_llm
from collection_assistant.tools.dispute_tools import (
    check_collection_hold,
    classify_dispute_type,
    get_active_disputes_data,
    get_dispute_history,
    get_resolution_timeline,
)

SYSTEM_PROMPT = """You are the Dispute Agent for an AI-powered debt collection assistant.
Your job is to identify all open disputes, classify their types, and flag any collection holds.

Produce a JSON response with these exact fields:
{
  "account_id": str,
  "active_disputes": [
    {"dispute_id": str, "dispute_type": str, "status": str, "opened_date": str,
     "description": str or null, "collection_hold": bool}
  ],
  "resolved_disputes": [
    {"dispute_id": str, "dispute_type": str, "status": str, "opened_date": str,
     "resolved_date": str or null, "resolution": str or null, "collection_hold": bool}
  ],
  "collection_hold": bool,
  "hold_reason": str or null,
  "total_open_disputes": int,
  "summary": "One paragraph summary of the dispute situation and its impact on collection"
}

CRITICAL rules (never violate):
- Copy collection_hold EXACTLY from the pre-calculated value provided
- If collection_hold = true, the summary must state outbound collection contact is NOT permitted
- dispute_type must be one of: billing_error | fraud_claim | identity_theft | service_dispute | payment_dispute

Respond with valid JSON only."""


def run_dispute_agent(state: CollectionWorkflowState) -> CollectionWorkflowState:
    account_id = state["account_id"]
    started_at = datetime.now(timezone.utc)

    state["agent_statuses"]["dispute"] = {
        "stage": 2, "status": "running",
        "started_at": started_at.isoformat(), "completed_at": None,
        "elapsed_ms": None, "error": None,
    }
    event_bus.emit(state["workflow_id"], "agent_update", {"agent": "dispute", "stage": 2, "status": "running", "elapsed_ms": None, "error": None})

    try:
        active = get_active_disputes_data(account_id)
        history = get_dispute_history(account_id)
        hold_data = check_collection_hold(account_id)
        timeline = get_resolution_timeline(account_id)

        resolved = [d for d in history if d.get("status") == "resolved"]

        # Enrich active disputes with classification and timeline
        for d in active:
            if not d.get("dispute_type") or d.get("dispute_type") == "billing_error":
                desc = d.get("description") or ""
                d["dispute_type"] = classify_dispute_type(desc)
            tl = next((t for t in timeline if t["dispute_id"] == d["dispute_id"]), {})
            d["days_open"] = tl.get("days_open", 0)
            d["escalated"] = tl.get("escalated", False)

        data_prompt = f"""Dispute data for account {account_id}:

ACTIVE DISPUTES (with classification + timeline): {json.dumps(active, indent=2)}
RESOLVED DISPUTES: {json.dumps(resolved, indent=2)}
PRE-CALCULATED VALUES (copy these exactly into your JSON output):
  collection_hold = {str(hold_data['collection_hold']).lower()}
  hold_reason = {json.dumps(hold_data['hold_reason']) if hold_data['hold_reason'] else 'null'}
  total_open_disputes = {len(active)}"""

        settings = get_settings()
        llm = get_llm("dispute", settings)
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=data_prompt),
        ])

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1].lstrip("json").strip()

        summary = json.loads(content)

        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["dispute_summary"] = summary
        state["agent_statuses"]["dispute"].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "dispute", "stage": 2, "status": "completed", "elapsed_ms": elapsed_ms, "error": None})
    except Exception as e:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["agent_statuses"]["dispute"].update({
            "status": "error", "error": str(e), "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "dispute", "stage": 2, "status": "error", "elapsed_ms": elapsed_ms, "error": str(e)})
        state["error_log"].append(f"dispute: {e}")

    return state


