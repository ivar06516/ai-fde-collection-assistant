"""Dispute Summary result card."""
import streamlit as st

DISPUTE_TYPE_LABELS = {
    "billing_error":    ("Billing Error",),
    "fraud_claim":      ("Fraud Claim",),
    "identity_theft":   ("Identity Theft",),
    "service_dispute":  ("Service Dispute",),
    "payment_dispute":  ("Payment Dispute",),
}
STATUS_COLORS = {
    "open":         "#C62828",
    "under_review": "#E65100",
    "escalated":    "#7B00CC",
    "resolved":     "#137333",
}


def render_dispute_card(summary: dict) -> None:
    st.markdown("### Dispute Summary", help="Active disputes on this account. A Collection Hold means no outbound contact is permitted until resolved.")
    if not summary:
        st.warning("No dispute data")
        return

    hold = summary.get("collection_hold", False)
    total = summary.get("total_open_disputes", 0)

    if hold:
        hold_reason = summary.get("hold_reason", "Active dispute")
        st.markdown(
            f'<div style="background:#FCE8E6;border-left:4px solid #C62828;'
            f'padding:0.8rem 1rem;border-radius:6px;margin-bottom:0.8rem">'
            f'<b style="color:#C62828">Collection Hold Active</b><br>'
            f'<span style="font-size:0.88rem;color:#555">{hold_reason}</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="background:#E6F4EA;border-left:4px solid #137333;'
            'padding:0.6rem 1rem;border-radius:6px;margin-bottom:0.8rem">'
            '<b style="color:#137333">No Collection Hold</b></div>',
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Open Disputes", total)
    with c2:
        resolved_count = len(summary.get("resolved_disputes", []))
        st.metric("Resolved", resolved_count)

    active = summary.get("active_disputes", [])
    if active:
        st.markdown("**Active Disputes**")
        for d in active:
            dtype = d.get("dispute_type", "dispute")
            label = DISPUTE_TYPE_LABELS.get(dtype, (dtype.replace("_"," ").title(),))[0]
            status = d.get("status", "open")
            s_color = STATUS_COLORS.get(status, "#333")
            days = d.get("days_open")
            escalated = d.get("escalated", False)
            with st.expander(f"{label}  —  {d.get('dispute_id', '')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f'**Status:** <span style="color:{s_color};font-weight:700">{status.replace("_"," ").title()}</span>', unsafe_allow_html=True)
                    st.markdown(f"**Opened:** {d.get('opened_date', '—')}")
                with col2:
                    if days is not None:
                        esc = "  ·  Escalated" if escalated else ""
                        st.markdown(f"**Duration:** {days} days{esc}")
                    hold_text = "Hold Active" if d.get("collection_hold") else "No Hold"
                    st.markdown(f"**Collection Hold:** {hold_text}")
                if d.get("description"):
                    st.caption(d["description"])

    if summary.get("summary"):
        with st.expander("Full Summary"):
            st.write(summary["summary"])
