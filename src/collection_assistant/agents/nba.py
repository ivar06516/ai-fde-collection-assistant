"""NBA Agent — synthesises all upstream outputs into the Next Best Action."""
import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from collection_assistant.config import get_settings
from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant.llm.client_factory import get_llm
from collection_assistant.tools.nba_tools import evaluate_action_eligibility, score_action_options

SYSTEM_PROMPT = """You are the Next Best Action (NBA) Agent for an AI-powered debt collection assistant.
You synthesise customer profile, account profile, arrears prediction, and dispute summary
to recommend the SINGLE best next collection action.

Available actions: initiate_call, send_sms, send_email, offer_payment_plan, offer_settlement,
place_on_hold, escalate_to_legal, flag_for_writeoff, no_action_required

HARD CONSTRAINTS (never violate):
- If collection_hold = true: ONLY recommend place_on_hold or no_action_required
- If account_status = legal: prefer escalate_to_legal or offer_settlement
- trajectory = critical + default_probability > 0.7: prefer escalate_to_legal or offer_settlement

Produce a JSON response with these exact fields:
{
  "action": str (one of the 9 actions above),
  "channel": str (e.g. "mobile", "email", "sms", "legal_team", "none"),
  "rationale": str (minimum 100 characters explaining WHY this action),
  "confidence_score": float (0.0-1.0),
  "urgency": "low|medium|high|critical",
  "alternative_actions": [
    {"action": str, "rationale": str, "confidence": float}
  ],
  "policy_constraints_applied": [list of constraint strings that affected the decision],
  "summary": "One sentence NBA recommendation summary"
}

Respond with valid JSON only."""


def run_nba_agent(state: CollectionWorkflowState) -> CollectionWorkflowState:
    started_at = datetime.now(timezone.utc)

    state["agent_statuses"]["nba"] = {
        "stage": 3, "status": "running",
        "started_at": started_at.isoformat(), "completed_at": None,
        "elapsed_ms": None, "error": None,
    }

    try:
        customer_profile = state.get("customer_profile") or {}
        account_profile = state.get("account_profile") or {}
        arrears_prediction = state.get("arrears_prediction") or {}
        dispute_summary = state.get("dispute_summary") or {}

        collection_hold = dispute_summary.get("collection_hold", False)
        trajectory = arrears_prediction.get("arrears_trajectory", "stable")
        dpd = account_profile.get("days_past_due", 0)
        account_status = account_profile.get("account_status", "current")
        default_prob = arrears_prediction.get("default_probability", 0.0)
        risk_segment = customer_profile.get("risk_segment", "medium")

        eligibility = evaluate_action_eligibility(collection_hold, trajectory, dpd, account_status)
        scored = score_action_options(
            eligibility["eligible_actions"], trajectory, dpd, default_prob, risk_segment
        )

        data_prompt = f"""All upstream agent outputs for NBA synthesis:

CUSTOMER PROFILE SUMMARY: {customer_profile.get('summary', 'N/A')}
- Risk segment: {risk_segment}
- Hardship flag: {customer_profile.get('hardship_flag', False)}
- Preferred channel: {customer_profile.get('preferred_channel', 'mobile')}

ACCOUNT PROFILE SUMMARY: {account_profile.get('summary', 'N/A')}
- Product: {account_profile.get('product_type', 'N/A')}
- Outstanding balance: ${account_profile.get('outstanding_balance', 0):,.2f}
- DPD: {dpd}
- Account status: {account_status}
- On-time rate: {account_profile.get('on_time_payment_rate', 1.0):.0%}

ARREARS PREDICTION SUMMARY: {arrears_prediction.get('summary', 'N/A')}
- Trajectory: {trajectory}
- Default probability: {default_prob:.0%}
- Predicted DPD @90 days: {arrears_prediction.get('predicted_dpd_90', dpd)}

DISPUTE SUMMARY: {dispute_summary.get('summary', 'N/A')}
- Collection hold: {collection_hold}
- Hold reason: {dispute_summary.get('hold_reason', 'None')}
- Open disputes: {dispute_summary.get('total_open_disputes', 0)}

ELIGIBLE ACTIONS (pre-filtered): {eligibility['eligible_actions']}
CONSTRAINTS: {eligibility['constraints']}
PRE-SCORED OPTIONS: {json.dumps(scored[:4], indent=2)}
TRIGGER CONTEXT: {state.get('trigger_context', 'routine_review')}"""

        settings = get_settings()
        llm = get_llm("nba", settings)
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=data_prompt),
        ])

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1].lstrip("json").strip()

        recommendation = json.loads(content)

        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["nba_recommendation"] = recommendation
        state["agent_statuses"]["nba"].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": elapsed_ms,
        })
    except Exception as e:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["agent_statuses"]["nba"].update({
            "status": "error", "error": str(e), "elapsed_ms": elapsed_ms,
        })
        state["error_log"].append(f"nba: {e}")

    return state
