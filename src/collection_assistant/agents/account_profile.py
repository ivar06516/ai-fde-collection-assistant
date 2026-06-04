"""Account Profile Agent — full account snapshot."""
import json
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from collection_assistant.config import get_settings
from collection_assistant.graph.state import CollectionWorkflowState
from collection_assistant import event_bus
from collection_assistant.llm.client_factory import get_llm
from collection_assistant.tools.account_tools import (
    get_account_balance,
    get_delinquency_status,
    get_linked_accounts,
    get_payment_history_summary,
)

SYSTEM_PROMPT = """You are the Account Profile Agent for an AI-powered debt collection assistant.
Your job is to produce a complete account snapshot from the provided data.

Produce a JSON response with these exact fields:
{
  "account_id": str,
  "customer_id": str,
  "product_type": str,
  "account_status": str,
  "outstanding_balance": float,
  "original_balance": float,
  "credit_limit": float or null,
  "days_past_due": int,
  "delinquency_start": str or null,
  "last_payment_date": str or null,
  "last_payment_amount": float or null,
  "next_due_date": str or null,
  "next_due_amount": float or null,
  "payment_history": [{"month": str, "amount_due": float, "amount_paid": float, "on_time": bool}],
  "on_time_payment_rate": float,
  "missed_payments_last_6m": int,
  "linked_account_ids": [list of account_id strings for other accounts held by this customer],
  "summary": "One-paragraph summary of the account status and payment behaviour"
}

IMPORTANT: copy these DB values exactly into your JSON (do not change them):
- account_status must be one of: current | delinquent | legal | written_off | closed

Respond with valid JSON only."""


def run_account_profile_agent(state: CollectionWorkflowState) -> CollectionWorkflowState:
    account_id = state["account_id"]
    started_at = datetime.now(timezone.utc)

    state["agent_statuses"]["account_profile"] = {
        "stage": 1, "status": "running",
        "started_at": started_at.isoformat(), "completed_at": None,
        "elapsed_ms": None, "error": None,
    }
    event_bus.emit(state["workflow_id"], "agent_update", {"agent": "account_profile", "stage": 1, "status": "running", "elapsed_ms": None, "error": None})

    try:
        balance = get_account_balance(account_id)
        delinquency = get_delinquency_status(account_id)
        payment_summary = get_payment_history_summary(account_id)
        linked = get_linked_accounts(account_id)

        data_prompt = f"""Account data to analyse:

BALANCE & PRODUCT: {json.dumps(balance, indent=2)}
DELINQUENCY STATUS: {json.dumps(delinquency, indent=2)}
PAYMENT HISTORY (12 months): {json.dumps(payment_summary, indent=2)}
LINKED ACCOUNTS: {json.dumps(linked, indent=2)}
CUSTOMER ID: {state['customer_id']}
IMPORTANT — copy these values exactly:
  account_status = "{delinquency['account_status']}"
  days_past_due = {delinquency['days_past_due']}
  outstanding_balance = {balance['outstanding_balance']}"""

        settings = get_settings()
        llm = get_llm("account_profile", settings)
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=data_prompt),
        ])

        from collection_assistant.agents import parse_llm_json
        content = parse_llm_json(response.content)

        profile = json.loads(content)

        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["account_profile"] = profile
        state["agent_statuses"]["account_profile"].update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "account_profile", "stage": 1, "status": "completed", "elapsed_ms": elapsed_ms, "error": None})
    except Exception as e:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        state["agent_statuses"]["account_profile"].update({
            "status": "error", "error": str(e), "elapsed_ms": elapsed_ms,
        })
        event_bus.emit(state["workflow_id"], "agent_update", {"agent": "account_profile", "stage": 1, "status": "error", "elapsed_ms": elapsed_ms, "error": str(e)})
        state["error_log"].append(f"account_profile: {e}")

    return state


