"""Account Profile result card."""
import streamlit as st

STATUS_COLORS = {"current": "🟢", "delinquent": "🟡", "legal": "🔴", "written_off": "⚫", "closed": "⚪"}


def render_account_card(profile: dict) -> None:
    st.markdown("### 🏦 Account Profile")
    if not profile:
        st.warning("No account profile data")
        return
    status = profile.get("account_status", "unknown")
    icon = STATUS_COLORS.get(status, "⚪")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Product", profile.get("product_type", "-"))
        st.metric("Status", f"{icon} {status}")
        st.metric("Outstanding", f"${profile.get('outstanding_balance', 0):,.2f}")
        st.metric("DPD", profile.get("days_past_due", 0))
    with col2:
        st.metric("Original Balance", f"${profile.get('original_balance', 0):,.2f}")
        st.metric("Last Payment", f"${profile.get('last_payment_amount', 0) or 0:,.2f}")
        st.metric("On-Time Rate", f"{profile.get('on_time_payment_rate', 1):.0%}")
        st.metric("Missed (6m)", profile.get("missed_payments_last_6m", 0))
    if profile.get("summary"):
        with st.expander("Full Summary"):
            st.write(profile["summary"])
