"""Customer Profile result card."""
import streamlit as st

RISK_COLORS = {"low": "🟢", "medium": "🟡", "high": "🔴", "hardship": "🟣"}


def render_customer_card(profile: dict) -> None:
    st.markdown("### 👤 Customer Profile")
    if not profile:
        st.warning("No customer profile data")
        return
    risk = profile.get("risk_segment", "unknown")
    risk_icon = RISK_COLORS.get(risk, "⚪")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Name", profile.get("full_name", "-"))
        st.metric("Age", profile.get("age", "-"))
        st.metric("Employment", profile.get("employment_status", "-"))
        st.metric("Annual Income", f"${profile.get('annual_income', 0) or 0:,.0f}")
    with col2:
        st.metric("Channel", profile.get("preferred_channel", "-"))
        st.metric("Preferred Time", profile.get("preferred_time", "-"))
        st.metric("Tenure", f"{profile.get('relationship_tenure_years', 0):.1f} yrs")
        st.metric("Risk Segment", f"{risk_icon} {risk}")
    if profile.get("hardship_flag"):
        st.warning(f"Hardship: {profile.get('hardship_reason', 'active')}")
    signals = profile.get("behavioural_signals", [])
    if signals:
        st.caption("Signals: " + " | ".join(signals))
    if profile.get("summary"):
        with st.expander("Full Summary"):
            st.write(profile["summary"])
