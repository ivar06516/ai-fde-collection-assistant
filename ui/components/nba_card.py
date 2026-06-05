"""NBA Recommendation card."""
import streamlit as st

ACTION_CONFIG = {
    "initiate_call":      ("Call Customer",      "#1565C0", "background:#E3F2FD;color:#1565C0"),
    "send_sms":           ("Send SMS",            "#2E7D32", "background:#E8F5E9;color:#2E7D32"),
    "send_email":         ("Send Email",          "#4527A0", "background:#EDE7F6;color:#4527A0"),
    "offer_payment_plan": ("Payment Plan",        "#E65100", "background:#FFF3E0;color:#E65100"),
    "offer_settlement":   ("Offer Settlement",    "#00695C", "background:#E0F2F1;color:#00695C"),
    "place_on_hold":      ("Place On Hold",       "#C62828", "background:#FCE8E6;color:#C62828"),
    "escalate_to_legal":  ("Escalate to Legal",   "#4A148C", "background:#F3E5F5;color:#4A148C"),
    "flag_for_writeoff":  ("Flag for Write-off",  "#333333", "background:#F3F3F3;color:#333"),
    "no_action_required": ("No Action Required",  "#137333", "background:#E6F4EA;color:#137333"),
}
URGENCY_CONFIG = {
    "low":      ("background:#E6F4EA;color:#137333", "LOW"),
    "medium":   ("background:#FFF3E0;color:#E65100", "MEDIUM"),
    "high":     ("background:#FCE8E6;color:#C62828", "HIGH"),
    "critical": ("background:#EDE7F6;color:#7B00CC", "CRITICAL"),
}
CHANNEL_ICON = {
    "mobile": "📱", "email": "📧", "sms": "💬", "legal_team": "⚖",
    "none": "—", "post": "✉", "phone": "📞",
}


def _badge(style, text):
    return (f'<span style="{style};padding:3px 12px;border-radius:12px;'
            f'font-size:0.78rem;font-weight:700">{text}</span>')


def render_nba_card(recommendation: dict) -> None:
    st.markdown("### Next Best Action", help="The AI-recommended collection action, synthesised from customer profile, arrears prediction, and dispute status.")
    if not recommendation:
        st.warning("No recommendation available")
        return

    action = recommendation.get("action", "unknown")
    channel = recommendation.get("channel", "none")
    confidence = recommendation.get("confidence_score", 0)
    urgency = recommendation.get("urgency", "medium")
    blocked = recommendation.get("blocked_by_dispute", False)

    action_label, action_color, action_badge_style = ACTION_CONFIG.get(
        action, (action.replace("_", " ").title(), "#333", "background:#eee;color:#333")
    )
    urgency_style, urgency_label = URGENCY_CONFIG.get(urgency, ("background:#eee;color:#333", urgency.upper()))
    ch_icon = CHANNEL_ICON.get(channel, "📬")
    conf_color = "#137333" if confidence >= 0.8 else "#E65100" if confidence >= 0.6 else "#C62828"

    # Main recommendation banner
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#A100FF0D,#fff);'
        f'border:2px solid #A100FF;border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1rem">'
        f'<div style="font-size:0.8rem;color:#616161;margin-bottom:0.3rem;font-weight:600;letter-spacing:0.05em">RECOMMENDED ACTION</div>'
        f'<div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">'
        f'<span style="{action_badge_style};padding:6px 16px;border-radius:20px;font-size:1.1rem;font-weight:800">{action_label}</span>'
        f'<span style="font-size:0.85rem;color:#666">{ch_icon} via <b>{channel.replace("_"," ").title()}</b></span>'
        f'</div>'
        f'<div style="display:flex;gap:1.5rem;margin-top:0.8rem;flex-wrap:wrap">'
        f'<div><span style="color:#616161;font-size:0.78rem">CONFIDENCE</span><br>'
        f'<span style="font-size:1.4rem;font-weight:800;color:{conf_color}">{confidence:.0%}</span></div>'
        f'<div><span style="color:#616161;font-size:0.78rem">URGENCY</span><br>'
        f'<span style="{urgency_style};padding:3px 10px;border-radius:10px;font-size:0.82rem;font-weight:700">{urgency_label}</span></div>'
        + (f'<div><span style="{action_badge_style.replace("background:","background:")};;padding:3px 10px;border-radius:10px;font-size:0.78rem;font-weight:700">Dispute Hold Applied</span></div>' if blocked else "")
        + f'</div></div>',
        unsafe_allow_html=True,
    )

    # Rationale
    st.markdown("**Rationale**")
    rationale = recommendation.get("rationale", "")
    st.markdown(
        f'<div style="background:#F8F8F8;border-left:3px solid #A100FF;'
        f'padding:0.8rem 1rem;border-radius:0 6px 6px 0;font-size:0.9rem;line-height:1.6">'
        f'{rationale}</div>',
        unsafe_allow_html=True,
    )

    # Policy constraints
    constraints = recommendation.get("policy_constraints_applied", [])
    if constraints:
        st.markdown("")
        for c in constraints:
            st.caption(f"Policy: {c}")

    # Alternative actions
    alternatives = recommendation.get("alternative_actions", [])
    if alternatives:
        st.markdown("")
        with st.expander(f"Alternative Actions ({len(alternatives)})"):
            for alt in alternatives:
                alt_action = alt.get("action", "")
                alt_label, _, alt_style = ACTION_CONFIG.get(alt_action, (alt_action.replace("_"," ").title(), "#333", "background:#eee;color:#333"))
                alt_conf = alt.get("confidence", 0)
                alt_rat = alt.get("rationale", "")
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f'<span style="{alt_style};padding:2px 8px;border-radius:8px;font-size:0.8rem;font-weight:700">{alt_label}</span>', unsafe_allow_html=True)
                    if alt_rat:
                        st.caption(alt_rat)
                with col_b:
                    st.markdown(f'<div style="text-align:right;font-weight:700;color:#666">{alt_conf:.0%}</div>', unsafe_allow_html=True)
                st.markdown("---")
