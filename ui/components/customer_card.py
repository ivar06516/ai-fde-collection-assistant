"""Customer Profile result card."""
import streamlit as st

RISK_BADGE = {
    "low":      ("background:#E6F4EA;color:#137333", "LOW RISK"),
    "medium":   ("background:#FFF3E0;color:#E65100", "MEDIUM RISK"),
    "high":     ("background:#FCE8E6;color:#C62828", "HIGH RISK"),
    "hardship": ("background:#EDE7F6;color:#4527A0", "HARDSHIP"),
}
CHANNEL_ICON = {"mobile": "📱", "email": "📧", "post": "✉️"}
TIME_ICON    = {"morning": "🌅", "afternoon": "☀️", "evening": "🌙"}


def _fmt(v: str) -> str:
    """Format snake_case enum to Title Case."""
    return str(v).replace("_", " ").title() if v else "—"


def _badge(style: str, text: str) -> str:
    return (f'<span style="{style};padding:3px 10px;border-radius:12px;'
            f'font-size:0.78rem;font-weight:700">{text}</span>')


def render_customer_card(profile: dict) -> None:
    st.markdown("### 👤 Customer Profile")
    if not profile:
        st.warning("No customer profile data")
        return

    risk = profile.get("risk_segment", "medium")
    style, label = RISK_BADGE.get(risk, ("background:#eee;color:#333", risk.upper()))
    channel = profile.get("preferred_channel", "mobile")
    pref_time = profile.get("preferred_time", "morning")

    # Risk badge + hardship warning inline
    col_badge, col_warn = st.columns([1, 2])
    with col_badge:
        st.markdown(_badge(style, label), unsafe_allow_html=True)
    with col_warn:
        if profile.get("hardship_flag"):
            st.markdown(
                _badge("background:#FCE8E6;color:#C62828",
                       f"⚠ HARDSHIP — {_fmt(profile.get('hardship_reason', 'active'))}"),
                unsafe_allow_html=True)

    st.markdown("")  # spacer

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Name**")
        st.markdown(f"### {profile.get('full_name', '—')}")
        st.markdown(f"**Age:** {profile.get('age', '—')} &nbsp;&nbsp; **Gender:** {profile.get('gender') or '—'}")

    with c2:
        st.markdown("**Employment**")
        st.markdown(f"### {_fmt(profile.get('employment_status', '—'))}")
        income = profile.get("annual_income") or 0
        st.markdown(f"**Annual Income:** ${income:,.0f}")

    with c3:
        st.markdown("**Contact Preference**")
        ch_icon = CHANNEL_ICON.get(channel, "📬")
        t_icon = TIME_ICON.get(pref_time, "⏰")
        st.markdown(f"### {ch_icon} {_fmt(channel)}")
        st.markdown(f"{t_icon} Preferred time: **{_fmt(pref_time)}**")

    st.markdown("---")
    c4, c5 = st.columns(2)
    with c4:
        tenure = profile.get("relationship_tenure_years", 0)
        st.metric("Customer Since", f"{tenure:.1f} years")
    with c5:
        interactions = profile.get("prior_collection_interactions", 0)
        last_outcome = _fmt(profile.get("last_interaction_outcome") or "none")
        st.metric("Prior Interactions", f"{interactions}", delta=None)
        if interactions:
            st.caption(f"Last outcome: {last_outcome}")

    signals = profile.get("behavioural_signals", [])
    if signals:
        st.caption("⚡ Signals: " + "  ·  ".join(signals))

    if profile.get("summary"):
        with st.expander("📝 Full Summary"):
            st.write(profile["summary"])
