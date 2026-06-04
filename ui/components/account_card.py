"""Account Profile result card."""
import streamlit as st

STATUS_BADGE = {
    "current":     ("background:#E6F4EA;color:#137333", "CURRENT"),
    "delinquent":  ("background:#FFF3E0;color:#E65100", "DELINQUENT"),
    "legal":       ("background:#FCE8E6;color:#C62828", "LEGAL"),
    "written_off": ("background:#F3F3F3;color:#333",   "WRITTEN OFF"),
    "closed":      ("background:#F3F3F3;color:#666",   "CLOSED"),
}
PRODUCT_LABELS = {
    "personal_loan": "Personal Loan",
    "credit_card":   "Credit Card",
    "mortgage":      "Mortgage",
    "auto_loan":     "Auto Loan",
    "overdraft":     "Overdraft",
}


def _badge(style, text):
    return (f'<span style="{style};padding:3px 10px;border-radius:12px;'
            f'font-size:0.78rem;font-weight:700">{text}</span>')


def _dpd_color(dpd):
    if dpd == 0:   return "#137333"
    if dpd <= 30:  return "#E65100"
    if dpd <= 90:  return "#C62828"
    return "#7B00CC"


def render_account_card(profile: dict) -> None:
    st.markdown("### Account Profile")
    if not profile:
        st.warning("No account profile data")
        return

    status = profile.get("account_status", "current")
    status_style, status_label = STATUS_BADGE.get(status, ("background:#eee;color:#333", status.upper()))
    product = PRODUCT_LABELS.get(profile.get("product_type", ""), profile.get("product_type", "—"))
    dpd = profile.get("days_past_due", 0)
    dpd_color = _dpd_color(dpd)
    otr = profile.get("on_time_payment_rate", 1.0)
    missed = profile.get("missed_payments_last_6m", 0)
    otr_color = "#137333" if otr >= 0.8 else "#E65100" if otr >= 0.5 else "#C62828"

    col_s, col_p = st.columns([1, 2])
    with col_s:
        st.markdown(_badge(status_style, status_label), unsafe_allow_html=True)
    with col_p:
        st.markdown(_badge("background:#F3E5F5;color:#4A148C", product), unsafe_allow_html=True)

    st.markdown("")

    c1, c2, c3 = st.columns(3)
    with c1:
        bal = profile.get("outstanding_balance", 0)
        orig = profile.get("original_balance", 1)
        pct = (bal / orig * 100) if orig else 0
        st.markdown("**Outstanding Balance**")
        st.markdown(f"### ${bal:,.2f}")
        st.caption(f"of ${orig:,.2f} original ({pct:.0f}% remaining)")
    with c2:
        st.markdown("**Days Past Due**")
        st.markdown(f'<div style="font-size:2rem;font-weight:800;color:{dpd_color}">{dpd}</div>', unsafe_allow_html=True)
        delinq = profile.get("delinquency_start")
        st.caption(f"Since: {delinq}" if delinq else "Account is current")
    with c3:
        st.markdown("**Payment Behaviour**")
        st.markdown(f'<div style="font-size:1.8rem;font-weight:800;color:{otr_color}">{otr:.0%}</div><div style="font-size:0.82rem;color:#666">On-time rate</div>', unsafe_allow_html=True)
        if missed:
            st.caption(f"{missed} missed in last 6 months")

    st.markdown("---")
    c4, c5, c6 = st.columns(3)
    with c4:
        st.metric("Last Payment", f"${profile.get('last_payment_amount') or 0:,.2f}")
        st.caption(f"Date: {profile.get('last_payment_date') or '—'}")
    with c5:
        st.metric("Next Due", f"${profile.get('next_due_amount') or 0:,.2f}")
        st.caption(f"Date: {profile.get('next_due_date') or '—'}")
    with c6:
        cl = profile.get("credit_limit")
        if cl:
            st.metric("Credit Limit", f"${cl:,.2f}")
        else:
            linked = profile.get("linked_account_ids", [])
            st.metric("Linked Accounts", len(linked))

    if profile.get("summary"):
        with st.expander("Full Summary"):
            st.write(profile["summary"])
