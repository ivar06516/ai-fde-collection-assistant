"""Arrears Prediction Agent — forward-looking arrears forecast."""
from datetime import datetime, timezone

from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant import event_bus
from collection_assistant.tools.arrears_tools import (
    analyse_payment_pattern,
    calculate_arrears_trajectory,
    estimate_future_arrears,
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
  "contributing_risk_factors": [{"name": str, "weight": float (0.0-1.0)}],
  "confidence_score": float (0.0-1.0),
  "summary": "One paragraph natural language prediction summary"
}

IMPORTANT rules:
- Copy arrears_trajectory EXACTLY from the pre-calculated value provided — do not change it
- Copy default_probability EXACTLY from the pre-calculated value — do not change it
- Copy predicted_dpd_30/60/90 EXACTLY from the pre-calculated values — do not change them
- contributing_risk_factors must be the provided list of dicts with name + weight
- If months_available < 3 then confidence_score must be < 0.5
Respond with valid JSON only."""


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

        months_available = len(payment_months)
        pattern = analyse_payment_pattern(payment_months)
        trajectory = calculate_arrears_trajectory(dpd, pattern["trend"], pattern["consecutive_missed"])
        default_prob = predict_default_probability(dpd, trajectory, risk_segment, on_time_rate)
        risk_factors = identify_risk_factors(dpd, trajectory, hardship_flag, employment_status, on_time_rate, missed_6m)
        forecast = estimate_future_arrears(dpd, trajectory, outstanding_balance,
                                           months_available=months_available)

        # Perf Fix 3: build prediction dict directly from deterministic tools
        # No LLM needed — all values are pre-calculated; LLM was just echoing them back
        prediction = {
            "current_arrears_band": _get_arrears_band(dpd),
            "arrears_trajectory": trajectory,
            "predicted_dpd_30": forecast["predicted_dpd_30"],
            "predicted_dpd_60": forecast["predicted_dpd_60"],
            "predicted_dpd_90": forecast["predicted_dpd_90"],
            "default_probability": default_prob,
            "predicted_arrears_amount": forecast["predicted_arrears_amount"],
            "contributing_risk_factors": risk_factors,
            "confidence_score": forecast["confidence_score"],
            "summary": (
                f"Arrears trajectory is {trajectory} with a {default_prob:.0%} default probability. "
                f"Current DPD is {dpd}. Predicted DPD at 90 days: {forecast['predicted_dpd_90']}. "
                f"Confidence: {forecast['confidence_score']:.0%}. "
                f"Top risk factor: {risk_factors[0]['name'] if risk_factors else 'None'}."
            ),
        }

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


