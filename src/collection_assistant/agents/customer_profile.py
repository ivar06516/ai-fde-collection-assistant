"""Customer Profile Agent — builds 360 degree customer view."""
import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from collection_assistant.config import get_settings
from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant import event_bus
from collection_assistant.llm.client_factory import get_llm
from collection_assistant.tools.customer_tools import (
    detect_hardship_signals,
    get_contact_preferences,
    get_customer_demographics,
    get_interaction_history_summary,
)

SYSTEM_PROMPT = """You are the Customer Profile Agent for an AI-powered debt collection assistant.
Your job is to build a comprehensive 360-degree customer profile from the provided data.

Analyse the data and produce a JSON response with these exact fields:
{
  "customer_id": str,
  "full_name": str,
  "age": int,
  "employment_status": str,
  "annual_income": float,
  "city": str,
  "state": str,
  "preferred_channel": str,
  "preferred_time": str,
  "relationship_tenure_years": float,
  "risk_segment": str,
  "hardship_flag": bool,
  "hardship_reason": str or null,
  "prior_collection_interactions": int,
  "last_interaction_outcome": str or null,
  "behavioural_signals": [list of strings],
  "summary": "One-paragraph natural language summary of the customer profile"
}

Be factual. Base everything on the data provided. Respond with valid JSON only."""


def run_customer_profile_agent(state: CollectionWorkflowState) -> CollectionWorkflowState:
    customer_id = state["customer_id"]
    started_at = datetime.now(timezone.utc)

    state["agent_statuses"]["customer_profile"] = {
        "stage": 1, "status": "running",
        "started_at": started_at.isoformat(), "completed_at": None,
        "elapsed_ms": None, "error": None,
    }
    event_bus.emit(state["workflow_id"], "agent_update", {"agent": "customer_profile", "stage": 1, "status": "running", "elapsed_ms": None, "error": None})

    try:
        demographics = get_customer_demographics(customer_id)
        prefs = get_contact_preferences(customer_id)
        interactions = get_interaction_history_summary(customer_id)
        hardship = detect_hardship_signals(customer_id)

        data_prompt = f"""Customer data to analyse:

DEMOGRAPHICS: {json.dumps(demographics, indent=2)}
CONTACT PREFERENCES: {json.dumps(prefs, indent=2)}
INTERACTION HISTORY: {json.dumps(interactions, indent=2)}
HARDSHIP SIGNALS: {json.dumps(hardship, indent=2)}
IMPORTANT - use exactly these DB-sourced values in your JSON output (do not change them):
  risk_segment = "{demographics.get('risk_segment', 'medium')}" <- copy this exactly
  hardship_flag = {demographics.get('hardship_flag', False)}
  hardship_reason = {json.dumps(demographics.get('hardship_reason'))}"""

        settings = get_settings()
        llm = get_llm("customer_profile", settings)
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=data_prompt),
        ])

        from collection_assistant.agents import parse_llm_json
        content = parse_llm_json(response.content)

        profile = json.loads(content)

        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["customer_profile"] = profile
        state["agent_statuses"]["customer_profile"].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "customer_profile", "stage": 1, "status": "completed", "elapsed_ms": elapsed_ms, "error": None})
    except Exception as e:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["agent_statuses"]["customer_profile"].update({
            "status": "error", "error": str(e), "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "customer_profile", "stage": 1, "status": "error", "elapsed_ms": elapsed_ms, "error": str(e)})
        state["error_log"].append(f"customer_profile: {e}")

    return state


