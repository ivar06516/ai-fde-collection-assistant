"""Page 3 — Customer Profile view (read-only, no LLM)."""
import streamlit as st
import plotly.graph_objects as go

PRODUCT_LABELS = {
    "personal_loan":"Personal Loan","credit_card":"Credit Card",
    "mortgage":"Mortgage","auto_loan":"Auto Loan","overdraft":"Overdraft",
}
STATUS_STYLE = {
    "current":"background:#E8F5E9;color:#2E7D32","delinquent":"background:#FFF3E0;color:#E65100",
    "legal":"background:#FFEBEE;color:#C62828","written_off":"background:#F5F5F5;color:#333",
}
RISK_STYLE = {
    "low":"background:#E8F5E9;color:#2E7D32","medium":"background:#FFF8E1;color:#E65100",
    "high":"background:#FFEBEE;color:#C62828","hardship":"background:#EDE7F6;color:#4527A0",
}
OUTCOME_COLOR = {
    "contacted":"#2E7D32","promise_to_pay":"#4527A0","payment_arranged":"#137333",
    "no_answer":"#E65100","refused":"#C62828",
}


def _badge(text, style):
    return f'<span style="{style};padding:3px 10px;border-radius:10px;font-size:0.75rem;font-weight:700">{text}</span>'


def _payment_chart(payment_history: list) -> go.Figure:
    months = [p["month"] for p in reversed(payment_history)]
    paid   = [p["amount_paid"] for p in reversed(payment_history)]
    colors = ["#2E7D32" if p["on_time"] else "#C62828" for p in reversed(payment_history)]
    fig = go.Figure(go.Bar(
        x=months, y=paid, marker_color=colors,
        text=[f"${v:,.0f}" for v in paid], textposition="outside",
        hovertemplate="<b>%{x}</b><br>Paid: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        title="Payment History (12 months) — 🟢 On Time  🔴 Missed",
        height=220, margin=dict(l=10,r=10,t=40,b=40),
        yaxis_title="Amount Paid ($)", showlegend=False,
        plot_bgcolor="white", paper_bgcolor="white",
    )
    fig.update_xaxes(tickangle=-45, tickfont_size=9)
    return fig


def render_customer_profile_page(detail: dict, on_run_analysis, runs: list = None, on_view_run=None) -> None:
    """Render the full customer profile page."""

    # ── Page header + breadcrumb ───────────────────────────────────────────
    b1, b2 = st.columns([5, 2])
    with b1:
        st.markdown(
            f'<div style="font-size:0.78rem;color:#888;margin-bottom:0.3rem">'
            f'<span style="cursor:pointer;color:#A100FF">Dashboard</span>'
            f' › Customer Profile</div>',
            unsafe_allow_html=True,
        )
        name = detail.get("full_name","—")
        risk = detail.get("risk_segment","medium")
        rs   = RISK_STYLE.get(risk,"background:#eee;color:#333")
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:0.8rem">'
            f'<h2 style="margin:0">{name}</h2>'
            f'<span style="{rs};padding:3px 12px;border-radius:10px;font-size:0.75rem;font-weight:700">'
            f'{risk.upper()} RISK</span>'
            + (f'<span style="background:#FCE8E6;color:#C62828;padding:3px 10px;border-radius:10px;'
               f'font-size:0.72rem;font-weight:700">⚠ HARDSHIP: {detail.get("hardship_reason","").upper()}</span>'
               if detail.get("hardship_flag") else "")
            + f'</div>'
            f'<div style="font-size:0.78rem;color:#888;margin-top:3px">'
            f'{detail.get("customer_id","—")} · Member since {detail.get("relationship_since","—")} '
            f'({detail.get("relationship_tenure_years",0):.1f} years)</div>',
            unsafe_allow_html=True,
        )
    with b2:
        accounts = detail.get("accounts", [])
        if accounts:
            accs = {f'{a["account_id"]} ({PRODUCT_LABELS.get(a["product_type"],a["product_type"])})': a
                    for a in accounts}
            chosen_label = st.selectbox("Select Account", list(accs.keys()),
                                         key="profile_acc_select", label_visibility="collapsed")
            chosen_acc = accs[chosen_label]
        else:
            chosen_acc = {}
        trigger = st.selectbox("Trigger", [
            "routine_review","missed_payment","hardship_claim",
            "dispute_raised","payment_arrangement_review","legal_referral_review",
        ], format_func=lambda x: x.replace("_"," ").title(),
           key="profile_trigger", label_visibility="collapsed")
        if st.button("▶ Run AI Analysis", type="primary", use_container_width=True):
            if chosen_acc:
                on_run_analysis(detail["customer_id"], chosen_acc["account_id"], trigger)

    st.markdown("---")

    # ── Section 1: Demographics + Contact ─────────────────────────────────
    st.markdown("#### Customer Overview")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Age", detail.get("age","—"))
        st.metric("Gender", detail.get("gender","—") or "—")
    with c2:
        st.metric("Employment", (detail.get("employment_status","—") or "—").replace("_"," ").title())
        income = detail.get("annual_income") or 0
        st.metric("Annual Income", f"${income:,.0f}")
    with c3:
        st.metric("Preferred Channel", (detail.get("preferred_channel","—") or "—").title())
        st.metric("Preferred Time", (detail.get("preferred_time","—") or "—").title())
    with c4:
        st.metric("City", detail.get("city","—") or "—")
        st.metric("State", detail.get("state","—") or "—")

    st.markdown("")

    # ── Section 2: All Accounts ────────────────────────────────────────────
    if accounts:
        st.markdown("#### Accounts")
        for acc in accounts:
            prod   = PRODUCT_LABELS.get(acc["product_type"], acc["product_type"])
            stat   = acc["account_status"]
            ss     = STATUS_STYLE.get(stat,"background:#eee;color:#333")
            dpd    = acc.get("days_past_due", 0)
            dpd_c  = "#C62828" if dpd>60 else "#E65100" if dpd>30 else "#2E7D32"
            otr    = acc.get("on_time_rate", 1.0)
            otr_c  = "#2E7D32" if otr>=0.8 else "#E65100" if otr>=0.5 else "#C62828"

            with st.expander(
                f"{prod} — {acc['account_id']}  |  "
                f"{'DPD: '+str(dpd) if dpd else 'Current'}  |  "
                f"${acc['outstanding_balance']:,.0f} outstanding",
                expanded=(acc["account_id"] == (chosen_acc.get("account_id") if chosen_acc else None)),
            ):
                ac1, ac2, ac3, ac4 = st.columns(4)
                with ac1:
                    st.markdown(_badge(stat.title(), ss), unsafe_allow_html=True)
                    st.metric("Outstanding", f"${acc['outstanding_balance']:,.2f}")
                    st.metric("Original", f"${acc['original_balance']:,.2f}")
                with ac2:
                    st.markdown(
                        f'<div style="font-size:2rem;font-weight:800;color:{dpd_c}">{dpd}</div>'
                        f'<div style="font-size:0.75rem;color:#888">Days Past Due</div>',
                        unsafe_allow_html=True)
                with ac3:
                    st.markdown(
                        f'<div style="font-size:1.6rem;font-weight:800;color:{otr_c}">{otr:.0%}</div>'
                        f'<div style="font-size:0.75rem;color:#888">On-Time Payment Rate</div>',
                        unsafe_allow_html=True)
                    missed = acc.get("missed_last_6m", 0)
                    if missed:
                        st.caption(f"⚠ {missed} missed in last 6 months")
                with ac4:
                    st.metric("Last Payment", f"${acc.get('last_payment_amount') or 0:,.0f}")
                    st.metric("Missed (6m)", acc.get("missed_last_6m", 0))

                # Payment history chart
                ph = acc.get("payment_history", [])
                if ph:
                    st.plotly_chart(_payment_chart(ph), use_container_width=True)

    st.markdown("")

    # ── Section 3: Disputes ────────────────────────────────────────────────
    disputes = detail.get("disputes", [])
    if disputes:
        st.markdown("#### Disputes")
        active   = [d for d in disputes if d["status"] in ("open","under_review","escalated")]
        resolved = [d for d in disputes if d["status"] == "resolved"]
        if active:
            for d in active:
                hold_badge = ("🚫 Hold Active" if d["collection_hold"] else "No Hold")
                hold_style = ("color:#C62828;font-weight:700" if d["collection_hold"] else "color:#2E7D32;font-weight:700")
                with st.expander(f"⚠ {d['type'].replace('_',' ').title()} — {d['dispute_id']} ({d['status'].title()})"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Opened:** {d['opened']}")
                        st.markdown(f"**Status:** {d['status'].replace('_',' ').title()}")
                    with col_b:
                        st.markdown(f"**Collection Hold:** <span style='{hold_style}'>{hold_badge}</span>",
                                    unsafe_allow_html=True)
                    if d.get("description"):
                        st.caption(d["description"])
        if resolved:
            st.caption(f"✅ {len(resolved)} resolved dispute(s)")

    # ── Section 4: Previous Analysis Runs ────────────────────────────────
    if runs:
        import streamlit as _st
        _st.markdown("#### Previous Analysis Runs")
        ACTION_COLORS = {
            "offer_settlement":"#00695C","escalate_to_legal":"#4A148C",
            "initiate_call":"#1565C0","place_on_hold":"#C62828",
            "no_action_required":"#137333","offer_payment_plan":"#E65100",
            "send_sms":"#2E7D32","send_email":"#4527A0","flag_for_writeoff":"#333",
        }
        for run in runs[:5]:
            action = run.get("nba_action","—")
            conf   = run.get("nba_confidence") or 0
            run_at = (run.get("created_at") or "")[:16]
            ms     = run.get("total_ms") or 0
            trigger= (run.get("trigger_context") or "").replace("_"," ").title()
            a_color= ACTION_COLORS.get(action,"#888")
            wf_id  = run.get("workflow_id","")
            cols = _st.columns([2, 2, 1.5, 1.5, 1])
            with cols[0]:
                _st.markdown(
                    f'<div style="font-weight:700;color:{a_color}">{action.replace("_"," ").title()}</div>'
                    f'<div style="font-size:0.72rem;color:#888">{trigger}</div>',
                    unsafe_allow_html=True)
            with cols[1]:
                _st.markdown(
                    f'<div style="font-size:0.85rem;color:#888">{run_at}</div>',
                    unsafe_allow_html=True)
            with cols[2]:
                _st.markdown(
                    f'<div style="font-weight:700;color:{a_color}">{conf:.0%}</div>'
                    f'<div style="font-size:0.7rem;color:#888">confidence</div>',
                    unsafe_allow_html=True)
            with cols[3]:
                _st.markdown(
                    f'<div style="font-size:0.82rem;color:#888">{ms/1000:.1f}s</div>',
                    unsafe_allow_html=True)
            with cols[4]:
                if _st.button("View", key=f"run_view_{wf_id}", use_container_width=True):
                    if on_view_run:
                        on_view_run(wf_id, detail["customer_id"])
            _st.markdown('<hr style="border:none;border-top:1px solid #F5F5F5;margin:2px 0">',
                         unsafe_allow_html=True)
        _st.markdown("")

    # ── Section 5: Interaction History ────────────────────────────────────
    interactions = detail.get("interactions", [])
    if interactions:
        st.markdown("#### Interaction History")
        for ix in interactions[:8]:
            outcome = ix.get("outcome","—") or "—"
            oc = OUTCOME_COLOR.get(outcome,"#666")
            st.markdown(
                f'<div style="display:flex;gap:0.8rem;align-items:flex-start;'
                f'padding:0.5rem 0;border-bottom:1px solid #F5F5F5">'
                f'<div style="font-size:0.72rem;color:#888;min-width:120px">'
                f'{str(ix.get("date",""))[:10]}</div>'
                f'<div style="font-size:0.78rem;font-weight:600;min-width:60px">'
                f'{(ix.get("type","") or "").title()}</div>'
                f'<div style="flex:1;font-size:0.78rem">{ix.get("notes","") or ""}</div>'
                f'<div style="font-size:0.72rem;font-weight:700;color:{oc}">{outcome.replace("_"," ").title()}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
