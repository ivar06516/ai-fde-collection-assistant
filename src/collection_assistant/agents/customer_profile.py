"""Customer Profile Agent — builds 360 degree customer view."""
import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from collection_assistant.config import get_settings
from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant import event_bus
from collection_assistant.llm.client_factory import get_llm
from collection_assistant.tools.customer_tools import get_all_customer_data

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
        # Perf Fix 4: single DB session for all customer data
        d = get_all_customer_data(customer_id)

        data_prompt = f"""Customer data to analyse:

NAME: {d["full_name"]}  AGE: {d["age"]}  EMPLOYMENT: {d["employment_status"]}  INCOME: ${d["annual_income"]:,.0f}
CITY: {d["city"]}, {d["state"]}  TENURE: {d["relationship_tenure_years"]} years
PRIOR INTERACTIONS: {d["prior_collection_interactions"]}  LAST OUTCOME: {d["last_outcome"]}
HARDSHIP SIGNALS: {d["behavioural_signals"]}

IMPORTANT - copy these DB values exactly:
  risk_segment = "{d["risk_segment"]}"
  hardship_flag = {d["hardship_flag"]}
  hardship_reason = {json.dumps(d["hardship_reason"])}
  preferred_channel = "{d["preferred_channel"]}"
  preferred_time = "{d["preferred_time"]}"
  relationship_tenure_years = {d["relationship_tenure_years"]}
  prior_collection_interactions = {d["prior_collection_interactions"]}"""

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


