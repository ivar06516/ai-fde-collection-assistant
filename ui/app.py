"""AI FDE Collection Assistant - 3-page Streamlit application.

Page 1: Dashboard  — portfolio view (customer list, KPIs, filters)
Page 2: Analysis   — pipeline execution + progressive results + audit trail
Page 3: Profile    — read-only customer profile (demographics, accounts, history)
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import streamlit as st

st.set_page_config(
    page_title="AI FDE Collection Assistant",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown("""<style>@keyframes spin{to{transform:rotate(360deg)}}</style>""", unsafe_allow_html=True)

# ── Imports ────────────────────────────────────────────────────────────────────
from ui.components.arrears_card import render_arrears_card
from ui.components.audit_panel import render_audit_panel
from ui.components.customer_profile_page import render_customer_profile_page
from ui.components.dashboard import render_dashboard
from ui.components.dispute_card import render_dispute_card
from ui.components.execution_panel import render_execution_panel
from ui.components.nba_card import render_nba_card
from ui.sse_client import (
    fetch_customer_detail, fetch_portfolio,
    get_workflow_state, trigger_pipeline,
)

PRODUCT_LABELS = {
    "personal_loan":"Personal Loan","credit_card":"Credit Card",
    "mortgage":"Mortgage","auto_loan":"Auto Loan","overdraft":"Overdraft",
}
RISK_STYLE = {
    "low":"background:#E8F5E9;color:#2E7D32","medium":"background:#FFF8E1;color:#E65100",
    "high":"background:#FFEBEE;color:#C62828","hardship":"background:#EDE7F6;color:#4527A0",
}

# ── Global header ──────────────────────────────────────────────────────────────
st.markdown("""<div style="background:#1A1A1A;padding:0.65rem 1.5rem;border-radius:8px;
margin-bottom:1rem;display:flex;align-items:center;gap:1rem">
<span style="color:#A100FF;font-size:1.2rem;font-weight:800">Accenture</span>
<span style="color:#555">|</span>
<span style="color:#ccc;font-size:0.9rem">AI FDE Collection Assistant</span>
</div>""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [
    ("page","dashboard"),     # dashboard | analysis | profile
    ("workflow_id",None),
    ("workflow_state",None),
    ("pipeline_row",None),    # portfolio row for customer banner on analysis page
    ("profile_customer_id",None),
    ("profile_detail",None),
    ("portfolio",None),
    ("dash_trigger","routine_review"),
    ("dash_selected",None),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Navigation")
    st.markdown("---")
    provider = os.environ.get("LLM_PROVIDER","free_cloud")
    icons = {"free_cloud":"🟢 Groq (Free)","local":"🟡 Ollama","premium":"🟣 Anthropic"}
    st.info(f"LLM: **{icons.get(provider,provider)}**")
    st.markdown("---")
    if st.button("🏠 Dashboard", use_container_width=True,
                 type="primary" if st.session_state.page=="dashboard" else "secondary"):
        st.session_state.page = "dashboard"
        st.session_state.dash_selected = None
        st.rerun()
    if st.session_state.page in ("analysis","profile"):
        if st.session_state.page == "profile" and st.session_state.profile_customer_id:
            row = next((r for r in (st.session_state.portfolio or [])
                        if r["customer_id"]==st.session_state.profile_customer_id), {})
            st.caption(f"Viewing: {row.get('full_name','Customer')}")
    st.markdown("---")
    if st.button("Seed Database"):
        import subprocess
        r = subprocess.run([sys.executable,"scripts/seed_db.py","--reset"],
            capture_output=True,text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        st.success("Seeded!") if r.returncode==0 else st.error(r.stderr[:200])
        st.session_state.portfolio = None
    if st.button("Refresh Portfolio"):
        st.session_state.portfolio = None
        st.rerun()


# ── Helper: customer banner (shared by Analysis page) ─────────────────────────
def _customer_banner(row: dict, wf_id: str = ""):
    name   = row.get("full_name","Customer")
    cid    = row.get("customer_id","")
    aid    = row.get("account_id","")
    risk   = row.get("risk_segment","medium")
    prod   = PRODUCT_LABELS.get(row.get("product_type",""), row.get("product_type",""))
    dpd    = row.get("days_past_due", 0)
    bal    = row.get("outstanding_balance", 0)
    rs     = RISK_STYLE.get(risk,"background:#eee;color:#333")
    dpd_c  = "#C62828" if dpd>60 else "#E65100" if dpd>30 else "#2E7D32"
    trigger = st.session_state.get("dash_trigger","routine_review").replace("_"," ").title()
    wf_span = (f'<span style="margin-left:auto;font-family:monospace;background:#F3E5F5;color:#4A148C;'
               f'padding:3px 10px;border-radius:8px;font-size:0.72rem;font-weight:700">{wf_id}</span>'
               if wf_id else "")
    st.markdown(
        f'<div style="background:#fff;border:1px solid #E0E0E0;border-radius:8px;'
        f'padding:0.7rem 1.2rem;margin-bottom:0.8rem;display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap">'
        f'<div><div style="font-size:1.05rem;font-weight:700">{name}</div>'
        f'<div style="font-size:0.72rem;color:#888;font-family:monospace">{cid} · {aid}</div></div>'
        f'<span style="color:#DDD">|</span>'
        f'<span style="{rs};padding:3px 10px;border-radius:10px;font-size:0.73rem;font-weight:700">'
        f'{risk.upper()} RISK</span>'
        f'<span style="color:#DDD">|</span><span style="font-size:0.85rem"><b>{prod}</b></span>'
        f'<span style="color:#DDD">|</span>'
        f'<span style="font-size:0.85rem">DPD: <b style="color:{dpd_c}">{dpd}</b></span>'
        f'<span style="color:#DDD">|</span>'
        f'<span style="font-size:0.85rem">Balance: <b>${bal:,.0f}</b></span>'
        f'<span style="color:#DDD">|</span>'
        f'<span style="font-size:0.85rem">Trigger: <b>{trigger}</b></span>'
        + wf_span + '</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "dashboard":
    st.markdown("## Portfolio Dashboard")

    if not st.session_state.portfolio:
        with st.spinner("Loading customer portfolio..."):
            data = fetch_portfolio()
            if data:
                st.session_state.portfolio = data
            else:
                st.error("Cannot reach backend. Start FastAPI on port 8000.")
                st.code("python -m uvicorn collection_assistant.api.main:app --port 8000")
                st.stop()

    def go_to_analysis(customer_id, account_id, trigger_context):
        with st.spinner("Starting analysis pipeline..."):
            try:
                wf_id = trigger_pipeline(customer_id, account_id, trigger_context)
                row = next((r for r in st.session_state.portfolio if r["customer_id"]==customer_id), {})
                st.session_state.workflow_id = wf_id
                st.session_state.pipeline_row = row
                st.session_state.dash_trigger = trigger_context
                st.session_state.page = "analysis"
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start pipeline: {e}")

    def go_to_profile(customer_id):
        st.session_state.profile_customer_id = customer_id
        st.session_state.profile_detail = None   # force reload
        st.session_state.page = "profile"
        st.rerun()

    render_dashboard(st.session_state.portfolio, go_to_analysis, on_view_customer=go_to_profile)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "analysis":
    wf_id   = st.session_state.workflow_id
    row     = st.session_state.get("pipeline_row") or {}

    # Breadcrumb
    bc1, bc2 = st.columns([6,1])
    with bc1:
        st.markdown(
            '<span style="font-size:0.78rem;color:#888">'
            '<a href="#" style="color:#A100FF;text-decoration:none">Dashboard</a>'
            ' › <b>Analysis</b></span>',
            unsafe_allow_html=True,
        )
    with bc2:
        if st.button("← Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()

    # Customer banner
    _customer_banner(row, wf_id)

    # Poll state
    state = get_workflow_state(wf_id) or {}
    agent_statuses = state.get("agent_statuses", {})
    workflow_status = state.get("workflow_status", "in_progress")

    # Progress bar
    done_count  = sum(1 for v in agent_statuses.values() if v.get("status")=="completed")
    in_run      = any(v.get("status")=="running" for v in agent_statuses.values())
    progress_pct = 100 if workflow_status=="completed" else min(int(done_count/6*95), 95)
    bar_color    = "#137333" if workflow_status=="completed" else "#A100FF"
    if workflow_status=="completed":
        prog_label = "Analysis complete"
    elif in_run:
        names = [k.replace("_"," ").title() for k,v in agent_statuses.items() if v.get("status")=="running"]
        prog_label = f"Running: {', '.join(names)}…"
    else:
        prog_label = "Initialising pipeline…"

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0.8rem;background:#fff;border:1px solid #E0E0E0;'
        f'border-radius:8px;padding:0.55rem 1.2rem;margin-bottom:0.8rem">'
        f'<span style="font-size:0.72rem;font-weight:600;color:#888;min-width:110px">Analysis Progress</span>'
        f'<div style="flex:1;height:6px;background:#EEE;border-radius:3px;overflow:hidden">'
        f'<div style="width:{progress_pct}%;height:100%;background:{bar_color};border-radius:3px;transition:width 0.4s ease"></div></div>'
        f'<span style="font-size:0.78rem;font-weight:700;color:{bar_color};min-width:32px">{progress_pct}%</span>'
        f'<span style="font-size:0.8rem;color:#888">{prog_label}</span></div>',
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1.4, 3], gap="medium")

    with col_left:
        render_execution_panel(agent_statuses)
        # "View Customer Profile" link
        st.markdown("")
        if st.button("👤 View Full Customer Profile", use_container_width=True):
            st.session_state.profile_customer_id = row.get("customer_id")
            st.session_state.profile_detail = None
            st.session_state.page = "profile"
            st.rerun()

    with col_right:
        # Summary zone: Complete banner + NBA
        nba_done = (agent_statuses.get("nba",{}).get("status")=="completed"
                    and state.get("nba_recommendation"))

        if workflow_status == "completed":
            nba_rec = state.get("nba_recommendation") or {}
            total_ms = state.get("total_ms", 0) or 0
            st.markdown(
                f'<div style="background:linear-gradient(90deg,#1B5E20,#2E7D32);color:white;'
                f'border-radius:10px;padding:0.8rem 1.2rem;display:flex;align-items:center;'
                f'gap:1rem;margin-bottom:0.8rem;flex-wrap:wrap">'
                f'<span style="font-size:1.3rem">✅</span>'
                f'<div style="flex:1">'
                f'<div style="font-weight:700">Analysis Complete — All 6 agents executed successfully</div>'
                f'<div style="font-size:0.82rem;opacity:0.85;margin-top:2px">'
                f'NBA: <b>{nba_rec.get("action","—").replace("_"," ").title()}</b>'
                f' · Confidence: <b>{nba_rec.get("confidence_score",0):.0%}</b></div></div>'
                f'<span style="background:rgba(255,255,255,0.2);padding:4px 12px;border-radius:8px;'
                f'font-size:0.8rem;font-weight:600">{total_ms/1000:.1f}s</span></div>',
                unsafe_allow_html=True,
            )

        if nba_done:
            render_nba_card(state.get("nba_recommendation") or {})

        if nba_done or workflow_status == "completed":
            st.markdown('<hr style="border:none;border-top:2px dashed #E8E8E8;margin:0.8rem 0 1rem">',
                        unsafe_allow_html=True)

        # Page 2 shows ONLY Stage 2 + Stage 3 agent results.
        # Customer Profile and Account Profile cards are on Page 3 only.
        arr = agent_statuses.get("arrears_prediction",{}).get("status") == "completed"
        dis = agent_statuses.get("dispute",{}).get("status") == "completed"
        s1_done = (agent_statuses.get("customer_profile",{}).get("status") == "completed"
                   or agent_statuses.get("account_profile",{}).get("status") == "completed")

        def _placeholder(icon, label):
            st.markdown(
                f'<div style="border:2px dashed #E8E8E8;border-radius:10px;padding:2rem;'
                f'text-align:center;color:#ccc"><div style="font-size:2rem">{icon}</div>'
                f'<div style="margin-top:0.4rem;font-size:0.85rem">{label}<br>Loading…</div></div>',
                unsafe_allow_html=True)

        # Stage 2 results
        if arr or dis:
            c3, c4 = st.columns(2)
            with c3:
                if arr:
                    dpd_now = (state.get("account_profile") or {}).get("days_past_due", 0)
                    render_arrears_card(state.get("arrears_prediction") or {}, current_dpd=dpd_now)
                else:
                    _placeholder("📊","Arrears Prediction")
            with c4:
                render_dispute_card(state.get("dispute_summary") or {}) if dis else _placeholder("⚖","Dispute Detection")

        if not s1_done:
            st.markdown('<div style="text-align:center;padding:3rem;color:#aaa">'
                        '<div style="font-size:3rem">⚙</div>'
                        '<div style="font-size:1rem;font-weight:600;margin-top:0.5rem">Pipeline Running</div>'
                        '<div style="font-size:0.85rem;margin-top:0.3rem">Agent outputs appear as each stage completes</div>'
                        '</div>', unsafe_allow_html=True)

        # Audit trail at bottom
        if agent_statuses.get("audit",{}).get("status") == "completed":
            render_audit_panel(state.get("audit_record") or {}, wf_id)

    # Keep polling
    if workflow_status not in ("completed","error"):
        time.sleep(1)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — CUSTOMER PROFILE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "profile":
    # Breadcrumb
    bc1, bc2 = st.columns([5, 1])
    with bc1:
        st.markdown(
            '<span style="font-size:0.78rem;color:#888">'
            '<a href="#" style="color:#A100FF;text-decoration:none">Dashboard</a>'
            ' › <b>Customer Profile</b></span>',
            unsafe_allow_html=True,
        )
    with bc2:
        if st.button("← Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()

    # Load customer detail
    cid = st.session_state.profile_customer_id
    if not st.session_state.profile_detail:
        with st.spinner("Loading customer profile..."):
            detail = fetch_customer_detail(cid)
            if detail:
                st.session_state.profile_detail = detail
            else:
                st.error(f"Could not load profile for {cid}")
                st.stop()

    detail = st.session_state.profile_detail

    def go_to_analysis_from_profile(customer_id, account_id, trigger_context):
        with st.spinner("Starting analysis..."):
            try:
                wf_id = trigger_pipeline(customer_id, account_id, trigger_context)
                row = next((r for r in (st.session_state.portfolio or []) if r["customer_id"]==customer_id), {})
                st.session_state.workflow_id = wf_id
                st.session_state.pipeline_row = row
                st.session_state.dash_trigger = trigger_context
                st.session_state.page = "analysis"
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start pipeline: {e}")

    render_customer_profile_page(detail, go_to_analysis_from_profile)
