from datetime import datetime, timezone


def build_audit_record(workflow_id: str, state: dict) -> dict:
    agent_steps = []
    for agent_name in ["customer_profile", "account_profile", "arrears_prediction",
                        "dispute_summary", "nba_recommendation"]:
        output = state.get(agent_name)
        status_info = state.get("agent_statuses", {}).get(agent_name, {})
        agent_steps.append({
            "agent": agent_name,
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
