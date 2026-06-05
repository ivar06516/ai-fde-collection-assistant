from datetime import datetime, timezone

# Maps output state key -> agent_statuses key (they differ for dispute and nba)
_AGENT_STATUS_KEYS = {
    "customer_profile":   "customer_profile",
    "account_profile":    "account_profile",
    "arrears_prediction": "arrears_prediction",
    "dispute_summary":    "dispute",           # state key differs from status key
    "nba_recommendation": "nba",               # state key differs from status key
}

# AC-007-01: ordered list of all 6 agents for lineage (audit is the 6th)
_AGENT_ORDER = list(_AGENT_STATUS_KEYS.items()) + [("audit_record", "audit")]


def build_audit_record(workflow_id: str, state: dict,
                        audit_elapsed_ms: int = 0) -> dict:
    """Build the full audit record from completed workflow state.

    AC-007-01: decision_lineage contains exactly 6 entries in pipeline order.
    AC-007-03: elapsed_ms populated from agent_statuses where available.
    """
    agent_steps = []
    for output_key, status_key in _AGENT_ORDER:
        output = state.get(output_key)
        status_info = state.get("agent_statuses", {}).get(status_key, {})

        # For audit agent entry, use the elapsed_ms passed in
        elapsed = (audit_elapsed_ms
                   if status_key == "audit"
                   else status_info.get("elapsed_ms"))

        agent_steps.append({
            "agent":       status_key,            # canonical name (dispute not dispute_summary)
            "stage":       status_info.get("stage"),
            "status":      status_info.get("status", "completed" if output else "unknown"),
            "elapsed_ms":  elapsed,
            "output_keys": list(output.keys()) if isinstance(output, dict) else [],
            "error":       status_info.get("error"),
        })

    nba = state.get("nba_recommendation") or {}
    dispute = state.get("dispute_summary") or {}

    return {
        "workflow_id":    workflow_id,
        "customer_id":    state.get("customer_id"),
        "account_id":     state.get("account_id"),
        "trigger_context":state.get("trigger_context"),
        "audit_timestamp":datetime.now(timezone.utc).isoformat(),
        "nba_action":     nba.get("action"),
        "nba_confidence": nba.get("confidence_score"),
        "nba_blocked_by_dispute": nba.get("blocked_by_dispute", False),
        "collection_hold":        dispute.get("collection_hold", False),
        "decision_lineage":       agent_steps,
        "workflow_status":        state.get("workflow_status"),
        "total_ms":               state.get("total_ms"),
        "error_count":            len(state.get("error_log", [])),
    }
