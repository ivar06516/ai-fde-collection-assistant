from datetime import datetime, timezone


_AGENT_STATUS_KEYS = {
    # output state key  ->  agent_statuses key
    "customer_profile":  "customer_profile",
    "account_profile":   "account_profile",
    "arrears_prediction":"arrears_prediction",
    "dispute_summary":   "dispute",          # state key differs from status key
    "nba_recommendation":"nba",              # state key differs from status key
}


def build_audit_record(workflow_id: str, state: dict) -> dict:
    agent_steps = []
    for output_key, status_key in _AGENT_STATUS_KEYS.items():
        output = state.get(output_key)
        status_info = state.get("agent_statuses", {}).get(status_key, {})
        agent_steps.append({
            "agent": output_key,
            "status": status_info.get("status", "unknown"),
            "elapsed_ms": status_info.get("elapsed_ms"),
            "output_keys": list(output.keys()) if isinstance(output, dict) else [],
        })
    nba = state.get("nba_recommendation") or {}
    return {
        "workflow_id": workflow_id,
        "customer_id": state.get("customer_id"),
        "account_id": state.get("account_id"),
        "trigger_context": state.get("trigger_context"),
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "nba_action": nba.get("action"),
        "nba_confidence": nba.get("confidence_score"),
        "decision_lineage": agent_steps,
        "workflow_status": state.get("workflow_status"),
        "total_ms": state.get("total_ms"),
    }
