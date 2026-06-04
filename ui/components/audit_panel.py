"""Expandable audit trail panel."""
import streamlit as st


def render_audit_panel(audit_record: dict, workflow_id: str) -> None:
    with st.expander("📋 Audit Trail"):
        if not audit_record:
            st.info(f"Audit record for {workflow_id} will appear here after pipeline completes")
            return
        st.markdown(f"**Workflow ID:** `{audit_record.get('workflow_id', workflow_id)}`")
        st.markdown(f"**Duration:** {audit_record.get('total_ms', '-')} ms")
        st.markdown(f"**Status:** {audit_record.get('workflow_status', '-')}")
        for step in audit_record.get("decision_lineage", []):
            icon = "✅" if step.get("status") == "completed" else "❌"
            st.markdown(
                f"{icon} **{step['agent']}** — {step.get('elapsed_ms', '?')}" +
                f"ms | Fields: {chr(44).join(step.get('output_keys', []))}")
