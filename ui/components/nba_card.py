"""NBA Recommendation card."""
import streamlit as st

ACTION_ICONS = {
    "initiate_call": "📞", "send_sms": "💬", "send_email": "📧",
    "offer_payment_plan": "📋", "offer_settlement": "🤝", "place_on_hold": "⏸",
    "escalate_to_legal": "⚖", "flag_for_writeoff": "✍", "no_action_required": "✅",
}
URGENCY_COLORS = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}


def render_nba_card(recommendation: dict) -> None:
    st.markdown("### ⭐ Next Best Action")
    if not recommendation:
        st.warning("No recommendation available")
        return
    action = recommendation.get("action", "unknown")
    icon = ACTION_ICONS.get(action, "▶")
    urgency = recommendation.get("urgency", "medium")
    confidence = recommendation.get("confidence_score", 0)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Action", f"{icon} {action.replace('_', ' ').title()}")
    with col2:
        st.metric("Channel", recommendation.get("channel", "-"))
    with col3:
        st.metric("Confidence", f"{confidence:.0%}")
    st.info(f"**Rationale:** {recommendation.get('rationale', 'N/A')}")
    constraints = recommendation.get("policy_constraints_applied", [])
    if constraints:
        st.caption("Constraints: " + " | ".join(constraints))
    alternatives = recommendation.get("alternative_actions", [])
    if alternatives:
        with st.expander("Alternative Actions"):
            for alt in alternatives:
                alt_icon = ACTION_ICONS.get(alt.get("action", ""), "▶")
                st.markdown(f"{alt_icon} **{alt.get('action', '').replace('_', ' ').title()}** ({alt.get('confidence', 0):.0%})")
                st.caption(alt.get("rationale", ""))
