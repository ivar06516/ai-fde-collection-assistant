"""Live agent execution timeline component."""
import streamlit as st

AGENT_LABELS = {
    "customer_profile": ("Stage 1", "Customer Profile"),
    "account_profile": ("Stage 1", "Account Profile"),
    "arrears_prediction": ("Stage 2", "Arrears Prediction"),
    "dispute": ("Stage 2", "Dispute Detection"),
    "nba": ("Stage 3", "Next Best Action"),
    "audit": ("Stage 3", "Audit Trail"),
}

STATUS_ICONS = {"waiting": "⏳", "running": "⟳", "completed": "✅", "error": "❌"}


def render_execution_panel(agent_statuses: dict) -> None:
    st.markdown("### Pipeline Execution")
    for agent_name, (stage_label, display_name) in AGENT_LABELS.items():
        status_info = agent_statuses.get(agent_name, {})
        status = status_info.get("status", "waiting")
        icon = STATUS_ICONS.get(status, "⏳")
        elapsed = status_info.get("elapsed_ms")
        elapsed_str = f"({elapsed}ms)" if elapsed else ""
        error = status_info.get("error")
        col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
        with col1:
            st.markdown(f"**{stage_label}**")
        with col2:
            st.markdown(f"{icon} {display_name}")
        with col3:
            st.markdown(f"`{status}` {elapsed_str}")
        with col4:
            if error:
                st.caption(f"⚠ {error[:50]}")
