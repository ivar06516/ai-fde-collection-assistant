"""Expandable audit trail panel."""
import streamlit as st

AGENT_LABELS = {
    "customer_profile":   ("Stage 1", "Customer Profile"),
    "account_profile":    ("Stage 1", "Account Profile"),
    "arrears_prediction": ("Stage 2", "Arrears Prediction"),
    "dispute_summary":    ("Stage 2", "Dispute Detection"),
    "nba_recommendation": ("Stage 3", "Next Best Action"),
}

STATUS_ICON = {
    "completed": ("✅", "#137333"),
    "error":     ("❌", "#C62828"),
    "running":   ("⟳",  "#E65100"),
    "waiting":   ("⏳", "#888"),
    "unknown":   ("⚠",  "#C62828"),
}


def _ms(value) -> str:
    if value is None:
        return "—"
    return f"{int(value):,} ms"


def _fmt_fields(keys: list) -> str:
    if not keys:
        return "—"
    friendly = [k.replace("_", " ").title() for k in keys[:6]]
    more = f" +{len(keys)-6} more" if len(keys) > 6 else ""
    return ", ".join(friendly) + more


def render_audit_panel(audit_record: dict, workflow_id: str) -> None:
    with st.expander("Audit Trail"):
        if not audit_record:
            st.info(f"Audit record for {workflow_id} will appear after pipeline completes.")
            return

        # Header row
        c1, c2, c3 = st.columns(3)
        with c1:
            wf = audit_record.get("workflow_id", workflow_id)
            st.markdown(f"**Workflow ID**")
            st.code(wf, language=None)
        with c2:
            total_ms = audit_record.get("total_ms")
            st.metric("Total Duration", _ms(total_ms))
        with c3:
            ws = audit_record.get("workflow_status", "—")
            color = "#137333" if ws == "completed" else "#C62828"
            st.markdown("**Status**")
            st.markdown(
                f'<span style="background:{color}1A;color:{color};'
                f'padding:4px 12px;border-radius:10px;font-weight:700;font-size:0.9rem">'.upper() + ws.upper() + '</span>',
                unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**Decision Lineage**")

        for step in audit_record.get("decision_lineage", []):
            agent = step.get("agent", "")
            stage_label, display_name = AGENT_LABELS.get(agent, ("—", agent))
            status = step.get("status", "unknown")
            icon, icon_color = STATUS_ICON.get(status, STATUS_ICON["unknown"])
            elapsed = _ms(step.get("elapsed_ms"))
            fields = _fmt_fields(step.get("output_keys", []))

            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:0.8rem;'
                f'padding:0.5rem 0;border-bottom:1px solid #F0F0F0">'
                f'<div style="min-width:28px;font-size:1.1rem;text-align:center">{icon}</div>'
                f'<div style="flex:1">'
                f'<div style="display:flex;gap:0.6rem;align-items:center;flex-wrap:wrap">'
                f'<b style="font-size:0.92rem">{display_name}</b>'
                f'<span style="background:#F3E5F5;color:#4A148C;padding:1px 7px;border-radius:8px;font-size:0.72rem;font-weight:600">{stage_label}</span>'
                f'<span style="color:#888;font-size:0.8rem">{elapsed}</span>'
                f'<span style="background:{icon_color}1A;color:{icon_color};padding:1px 7px;border-radius:8px;font-size:0.72rem;font-weight:600">{status.upper()}</span>'
                f'</div>'
                f'<div style="font-size:0.78rem;color:#666;margin-top:2px">Fields: {fields}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        # NBA decision summary
        nba_action = audit_record.get("nba_action")
        nba_conf = audit_record.get("nba_confidence")
        if nba_action:
            st.markdown("")
            st.markdown(
                f'<div style="background:#F3E5F5;border-radius:8px;padding:0.7rem 1rem;margin-top:0.5rem">'
                f'<b style="color:#4A148C">NBA Decision:</b> '
                f'<span style="font-weight:700">{nba_action.replace("_"," ").title()}</span>'
                + (f' &nbsp; <span style="color:#888;font-size:0.85rem">Confidence: {nba_conf:.0%}</span>' if nba_conf else "")
                + '</div>',
                unsafe_allow_html=True,
            )
