"""Arrears Prediction Agent — forward-looking arrears forecast."""
import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from collection_assistant.config import get_settings
from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant import event_bus
from collection_assistant.llm.client_factory import get_llm
from collection_assistant.tools.arrears_tools import (
    analyse_payment_pattern,
    calculate_arrears_trajectory,
    identify_risk_factors,
    predict_default_probability,
)

SYSTEM_PROMPT = """You are the Arrears Prediction Agent for an AI-powered debt collection assistant.
Using the payment pattern analysis and account data provided, forecast the arrears trajectory.

Produce a JSON response with these exact fields:
{
  "current_arrears_band": "current|1-30|31-60|61-90|90+",
  "arrears_trajectory": "improving|stable|deteriorating|critical",
  "predicted_dpd_30": int,
  "predicted_dpd_60": int,
  "predicted_dpd_90": int,
  "default_probability": float (0.0-1.0),
  "predicted_arrears_amount": float,
  "contributing_risk_factors": [list of strings],
  "confidence_score": float (0.0-1.0),
  "summary": "One paragraph natural language prediction summary"
}

Use the pre-calculated trajectory and probability as a starting point but apply your reasoning
to refine them. Respond with valid JSON only."""


def _get_arrears_band(dpd: int) -> str:
    if dpd == 0:
        return "current"
    if dpd <= 30:
        return "1-30"
    if dpd <= 60:
        return "31-60"
    if dpd <= 90:
        return "61-90"
    return "90+"


def run_arrears_prediction_agent(state: CollectionWorkflowState) -> CollectionWorkflowState:
    started_at = datetime.now(timezone.utc)

    state["agent_statuses"]["arrears_prediction"] = {
        "stage": 2, "status": "running",
        "started_at": started_at.isoformat(), "completed_at": None,
        "elapsed_ms": None, "error": None,
    }
    event_bus.emit(state["workflow_id"], "agent_update", {"agent": "arrears_prediction", "stage": 2, "status": "running", "elapsed_ms": None, "error": None})

    try:
        customer_profile = state.get("customer_profile") or {}
        account_profile = state.get("account_profile") or {}

        dpd = account_profile.get("days_past_due", 0)
        payment_months = account_profile.get("payment_history", [])
        on_time_rate = account_profile.get("on_time_payment_rate", 1.0)
        missed_6m = account_profile.get("missed_payments_last_6m", 0)
        risk_segment = customer_profile.get("risk_segment", "medium")
        hardship_flag = customer_profile.get("hardship_flag", False)
        employment_status = customer_profile.get("employment_status", "employed")
        outstanding_balance = account_profile.get("outstanding_balance", 0.0)

        pattern = analyse_payment_pattern(payment_months)
        trajectory = calculate_arrears_trajectory(dpd, pattern["trend"], pattern["consecutive_missed"])
        default_prob = predict_default_probability(dpd, trajectory, risk_segment, on_time_rate)
        risk_factors = identify_risk_factors(dpd, trajectory, hardship_flag, employment_status, on_time_rate, missed_6m)

        data_prompt = f"""Account and customer data for arrears prediction:

CURRENT DPD: {dpd}
OUTSTANDING BALANCE: ${outstanding_balance:,.2f}
PAYMENT PATTERN ANALYSIS: {json.dumps(pattern, indent=2)}
CALCULATED TRAJECTORY: {trajectory}
CALCULATED DEFAULT PROBABILITY: {default_prob}
RISK FACTORS: {json.dumps(risk_factors, indent=2)}
RISK SEGMENT: {risk_segment}
HARDSHIP FLAG: {hardship_flag}
EMPLOYMENT: {employment_status}
ARREARS BAND: {_get_arrears_band(dpd)}"""

        settings = get_settings()
        llm = get_llm("arrears_prediction", settings)
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=data_prompt),
        ])

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1].lstrip("json").strip()

        prediction = json.loads(content)

        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["arrears_prediction"] = prediction
        state["agent_statuses"]["arrears_prediction"].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "arrears_prediction", "stage": 2, "status": "completed", "elapsed_ms": elapsed_ms, "error": None})
    except Exception as e:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["agent_statuses"]["arrears_prediction"].update({
            "status": "error", "error": str(e), "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "arrears_prediction", "stage": 2, "status": "error", "elapsed_ms": elapsed_ms, "error": str(e)})
        state["error_log"].append(f"arrears_prediction: {e}")

    return state


