"""Dispute Summary result card."""
import streamlit as st


def render_dispute_card(summary: dict) -> None:
    st.markdown("### ⚖ Dispute Summary")
    if not summary:
        st.warning("No dispute data")
        return
    hold = summary.get("collection_hold", False)
    if hold:
        st.error(f"Collection Hold Active — {summary.get('hold_reason', 'Dispute pending')}")
    else:
        st.success("No collection hold")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Open Disputes", summary.get("total_open_disputes", 0))
    with col2:
        st.metric("Collection Hold", "YES" if hold else "NO")
    for d in summary.get("active_disputes", []):
        with st.expander(f"{d.get('dispute_type')} — {d.get('status')}"):
            st.write(f"ID: {d.get('dispute_id')} | Opened: {d.get('opened_date')}")
            st.write(d.get("description", "N/A"))
    if summary.get("summary"):
        with st.expander("Full Summary"):
            st.write(summary["summary"])
