"""Customer Portfolio Dashboard — Screen 0 of the AI Collection Assistant."""
import streamlit as st

RISK_STYLE = {
    "low":      "background:#E8F5E9;color:#2E7D32",
    "medium":   "background:#FFF8E1;color:#E65100",
    "high":     "background:#FFEBEE;color:#C62828",
    "hardship": "background:#EDE7F6;color:#4527A0",
}
STATUS_STYLE = {
    "current":     "background:#E8F5E9;color:#2E7D32",
    "delinquent":  "background:#FFF3E0;color:#E65100",
    "legal":       "background:#FFEBEE;color:#C62828",
    "written_off": "background:#F5F5F5;color:#333",
    "closed":      "background:#F5F5F5;color:#666",
}
PRODUCT_LABELS = {
    "personal_loan": "Personal Loan",
    "credit_card":   "Credit Card",
    "mortgage":      "Mortgage",
    "auto_loan":     "Auto Loan",
    "overdraft":     "Overdraft",
}
DPD_COLOR = {
    "current": "#2E7D32",
    "1-30":    "#E65100",
    "31-60":   "#C62828",
    "61-90":   "#C62828",
    "90+":     "#7B00CC",
}


def _badge(text, style):
    return (f'<span style="{style};padding:2px 8px;border-radius:9px;'
            f'font-size:0.72rem;font-weight:700;white-space:nowrap">{text}</span>')


def _kpi(label, value, sub, color):
    return (f'<div style="background:#fff;border:1px solid #E0E0E0;border-radius:10px;'
            f'padding:1rem 1.2rem;border-top:3px solid {color}">'
            f'<div style="font-size:0.72rem;color:#888;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:0.05em;margin-bottom:0.4rem">{label}</div>'
            f'<div style="font-size:2rem;font-weight:800;color:{color};line-height:1">{value}</div>'
            f'<div style="font-size:0.75rem;color:#888;margin-top:0.3rem">{sub}</div></div>')


def render_dashboard(portfolio, on_run_analysis, on_view_customer=None, on_view_run=None):
    """Render the customer portfolio dashboard."""
    total        = len(portfolio)
    delinquent   = sum(1 for r in portfolio if r["account_status"] == "delinquent")
    legal_count  = sum(1 for r in portfolio if r["account_status"] == "legal")
    hardship_count = sum(1 for r in portfolio if r["hardship_flag"])
    current_n    = sum(1 for r in portfolio if r["account_status"] == "current")
    active_holds = sum(1 for r in portfolio if r["collection_hold"])
    pct_delinq   = int(delinquent / total * 100) if total else 0
    pct_legal    = int(legal_count / total * 100) if total else 0

    # KPI Row
    k1, k2, k3, k4, k5 = st.columns(5)
    for col, label, val, sub, color in [
        (k1, "Total Customers",  total,          f"{total} accounts linked",          "#A100FF"),
        (k2, "Delinquent",       delinquent,     f"{pct_delinq}% of portfolio",       "#C62828"),
        (k3, "Legal Status",     legal_count,    f"{pct_legal}% escalated",           "#E65100"),
        (k4, "Hardship Flagged", hardship_count, f"Active holds: {active_holds}",     "#4527A0"),
        (k5, "Current",          current_n,      "In good standing",                  "#137333"),
    ]:
        with col:
            st.markdown(_kpi(label, val, sub, color), unsafe_allow_html=True)

    st.markdown("")

    # Filter Row
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([3, 2, 2, 2, 2, 2])
    with fc1:
        search = st.text_input("Search", placeholder="Name, Customer ID, Account…",
                               label_visibility="collapsed", key="dash_search")
    with fc2:
        risk_filter = st.selectbox("Risk", ["All Risk", "low", "medium", "high", "hardship"],
                                    format_func=lambda x: x if x == "All Risk" else x.title(),
                                    label_visibility="collapsed", key="dash_risk")
    with fc3:
        status_filter = st.selectbox("Status", ["All Status", "current", "delinquent", "legal"],
                                      format_func=lambda x: x if x == "All Status" else x.title(),
                                      label_visibility="collapsed", key="dash_status")
    with fc4:
        product_filter = st.selectbox("Product",
                                       ["All Products"] + list(PRODUCT_LABELS.keys()),
                                       format_func=lambda x: x if x == "All Products" else PRODUCT_LABELS.get(x, x),
                                       label_visibility="collapsed", key="dash_product")
    with fc5:
        hold_filter = st.selectbox("Hold", ["All", "Hold Active", "No Hold"],
                                    label_visibility="collapsed", key="dash_hold")
    with fc6:
        dpd_filter = st.selectbox("DPD",
                                   ["All DPD", "0 (Current)", "1-30", "31-60", "61-90", "90+"],
                                   label_visibility="collapsed", key="dash_dpd")

    # Apply filters
    filtered = list(portfolio)
    if search:
        q = search.lower()
        filtered = [r for r in filtered
                    if q in r["full_name"].lower()
                    or q in r["customer_id"].lower()
                    or q in r["account_id"].lower()
                    or q in (r.get("product_type") or "").lower()]
    if risk_filter != "All Risk":
        filtered = [r for r in filtered if r["risk_segment"] == risk_filter]
    if status_filter != "All Status":
        filtered = [r for r in filtered if r["account_status"] == status_filter]
    if product_filter != "All Products":
        filtered = [r for r in filtered if r["product_type"] == product_filter]
    if hold_filter == "Hold Active":
        filtered = [r for r in filtered if r["collection_hold"]]
    elif hold_filter == "No Hold":
        filtered = [r for r in filtered if not r["collection_hold"]]
    dpd_ranges = {"0 (Current)": (0, 0), "1-30": (1, 30), "31-60": (31, 60),
                  "61-90": (61, 90), "90+": (91, 9999)}
    if dpd_filter in dpd_ranges:
        lo, hi = dpd_ranges[dpd_filter]
        filtered = [r for r in filtered if lo <= (r["days_past_due"] or 0) <= hi]

    # Table header
    h1, h2 = st.columns([4, 2])
    with h1:
        st.markdown(
            f"**Customer List** &nbsp;"
            f"<span style='color:#888;font-size:0.85rem'>{len(filtered)} of {total} customers</span>",
            unsafe_allow_html=True)
    with h2:
        sel = st.session_state.get("dash_selected")
        if sel:
            if st.button(f"Run Analysis for {sel['name']}", type="primary",
                         use_container_width=True, key="run_selected_top"):
                on_run_analysis(sel["customer_id"], sel["account_id"],
                                st.session_state.get("dash_trigger", "routine_review"))

    if not filtered:
        st.info("No customers match the current filters.")
        return

    # Column headers
    h_cols = st.columns([3, 1.5, 2, 1.5, 1, 2, 1.5, 2, 2])
    for col_widget, label in zip(h_cols, ["Customer", "Risk", "Product", "Status",
                                           "DPD", "Outstanding", "Hold", "Last Run", "Actions"]):
        with col_widget:
            st.markdown(
                f'<div style="font-size:0.72rem;font-weight:700;color:#888;'
                f'text-transform:uppercase;letter-spacing:0.04em;'
                f'padding-bottom:4px;border-bottom:2px solid #E0E0E0">{label}</div>',
                unsafe_allow_html=True)

    # Customer rows
    for row in filtered:
        cid     = row["customer_id"]
        aid     = row["account_id"]
        name    = row["full_name"]
        risk    = row["risk_segment"]
        prod    = PRODUCT_LABELS.get(row["product_type"], row["product_type"])
        stat    = row["account_status"]
        dpd     = row.get("days_past_due", 0) or 0
        bal     = row.get("outstanding_balance", 0) or 0
        hold    = row.get("collection_hold", False)
        hship   = row.get("hardship_flag", False)
        hreason = row.get("hardship_reason")
        band    = row.get("arrears_band", "current")
        dpd_clr = DPD_COLOR.get(band, "#333")
        is_sel  = (st.session_state.get("dash_selected") or {}).get("customer_id") == cid

        c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([3, 1.5, 2, 1.5, 1, 2, 1.5, 2, 2])
        with c1:
            bg = "#F3E5F5" if is_sel else "transparent"
            hp_html = (f'<div style="font-size:0.7rem;color:#4527A0">Hardship: {hreason or "Active"}</div>'
                       if hship else "")
            st.markdown(
                f'<div style="background:{bg};border-radius:5px;padding:3px 6px">'
                f'<b style="font-size:0.88rem">{name}</b>'
                f'<div style="font-size:0.7rem;color:#888;font-family:monospace">{cid} · {aid}</div>'
                + hp_html + '</div>',
                unsafe_allow_html=True)
        with c2:
            rs = RISK_STYLE.get(risk, "background:#eee;color:#333")
            st.markdown(_badge(risk.upper(), rs), unsafe_allow_html=True)
        with c3:
            st.markdown(_badge(prod, "background:#EDE7F6;color:#4527A0"), unsafe_allow_html=True)
        with c4:
            ss = STATUS_STYLE.get(stat, "background:#eee;color:#333")
            st.markdown(_badge(stat.title(), ss), unsafe_allow_html=True)
        with c5:
            st.markdown(
                f'<div style="font-size:1.1rem;font-weight:800;color:{dpd_clr}">{dpd}</div>',
                unsafe_allow_html=True)
        with c6:
            st.markdown(f'<div style="font-size:0.9rem;font-weight:600">${bal:,.0f}</div>',
                        unsafe_allow_html=True)
        with c7:
            if hold:
                st.markdown(_badge("Hold Active", "background:#FFEBEE;color:#C62828"),
                            unsafe_allow_html=True)
            else:
                st.markdown(_badge("No Hold", "background:#E8F5E9;color:#137333"),
                            unsafe_allow_html=True)
        with c8:
            lr = row.get("last_run")
            if lr:
                action_label = (lr.get("nba_action") or "").replace("_"," ").title()
                conf = lr.get("nba_confidence") or 0
                run_at = (lr.get("run_at") or "")[:16]
                st.markdown(
                    f'<div style="font-size:0.75rem;font-weight:700;color:#A100FF">{action_label}</div>'
                    f'<div style="font-size:0.68rem;color:#888">{conf:.0%} · {run_at}</div>',
                    unsafe_allow_html=True)
                if st.button("View", key=f"view_run_{cid}", use_container_width=True):
                    if on_view_run:
                        on_view_run(lr["workflow_id"], cid)
            else:
                st.markdown('<div style="font-size:0.75rem;color:#ccc">No runs yet</div>',
                            unsafe_allow_html=True)
        with c9:
            if st.button("👤 Profile", key=f"view_{cid}", use_container_width=True):
                if on_view_customer:
                    on_view_customer(cid)
            if st.button("▶ Analyse", key=f"btn_{cid}_{aid}", use_container_width=True,
                         type="primary"):
                st.session_state.dash_selected = {
                    "customer_id": cid, "account_id": aid, "name": name,
                }
                on_run_analysis(cid, aid, st.session_state.get("dash_trigger", "routine_review"))

        st.markdown(
            '<hr style="margin:2px 0;border:none;border-top:1px solid #F0F0F0">',
            unsafe_allow_html=True)

    # Selected customer panel
    sel = st.session_state.get("dash_selected")
    if sel:
        sel_row = next((r for r in portfolio if r["customer_id"] == sel["customer_id"]), None)
        if sel_row:
            st.markdown("")
            st.markdown(
                f'<div style="border:2px solid #A100FF;border-radius:10px;'
                f'padding:0.8rem 1.2rem;background:#FAFAFA">'
                f'<span style="color:#A100FF;font-weight:700">Selected: '
                f'{sel["name"]} ({sel["customer_id"]} / {sel["account_id"]})</span>'
                f'</div>',
                unsafe_allow_html=True)
            sp1, sp2, sp3, sp4, sp5 = st.columns(5)
            with sp1:
                trigger = st.selectbox(
                    "Trigger Context",
                    ["routine_review", "missed_payment", "hardship_claim",
                     "dispute_raised", "payment_arrangement_review", "legal_referral_review"],
                    format_func=lambda x: x.replace("_", " ").title(),
                    key="dash_trigger",
                )
            with sp2:
                st.metric("Risk", sel_row["risk_segment"].upper())
            with sp3:
                st.metric("DPD", sel_row.get("days_past_due", 0))
            with sp4:
                st.metric("Outstanding", f"${sel_row.get('outstanding_balance', 0):,.0f}")
            with sp5:
                if st.button("Run Analysis", type="primary",
                             use_container_width=True, key="run_panel_btn"):
                    on_run_analysis(sel["customer_id"], sel["account_id"], trigger)
