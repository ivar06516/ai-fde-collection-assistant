"""AI FDE Collection Assistant - Main Streamlit application."""
import sys
import os
import time
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

# Spinner keyframe injected once
st.markdown("""<style>
@keyframes spin{to{transform:rotate(360deg)}}
.stApp > header {display:none}
</style>""", unsafe_allow_html=True)

from ui.components.arrears_card import render_arrears_card
from ui.components.account_card import render_account_card
from ui.components.audit_panel import render_audit_panel
from ui.components.customer_card import render_customer_card
from ui.components.dashboard import render_dashboard
from ui.components.dispute_card import render_dispute_card
from ui.components.execution_panel import render_execution_panel
from ui.components.nba_card import render_nba_card
from ui.sse_client import fetch_portfolio, get_workflow_state, trigger_pipeline

PRODUCT_LABELS = {
    "personal_loan": "Personal Loan", "credit_card": "Credit Card",
    "mortgage": "Mortgage", "auto_loan": "Auto Loan", "overdraft": "Overdraft",
}
RISK_STYLE = {"low":"background:#E8F5E9;color:#2E7D32","medium":"background:#FFF8E1;color:#E65100",
              "high":"background:#FFEBEE;color:#C62828","hardship":"background:#EDE7F6;color:#4527A0"}

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""<div style="background:#1A1A1A;padding:0.65rem 1.5rem;border-radius:8px;
margin-bottom:1rem;display:flex;align-items:center;gap:1rem">
<span style="color:#A100FF;font-size:1.2rem;font-weight:800">Accenture</span>
<span style="color:#555">|</span>
<span style="color:#ccc;font-size:0.9rem">AI FDE Collection Assistant</span>
</div>""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [("screen","dashboard"),("workflow_id",None),("workflow_state",None),
             ("dash_selected",None),("portfolio",None),("pipeline_row",None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### FDE Collection Assistant")
    st.caption("Multi-Agent Architecture PoC")
    st.markdown("---")
    provider = os.environ.get("LLM_PROVIDER","free_cloud")
    icons = {"free_cloud":"🟢 Groq (Free)","local":"🟡 Ollama","premium":"🟣 Anthropic"}
    st.info(f"LLM: **{icons.get(provider,provider)}**")
    st.markdown("---")
    if st.button("Seed Database"):
        import subprocess
        r = subprocess.run([sys.executable,"scripts/seed_db.py","--reset"],
            capture_output=True,text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if r.returncode==0:
            st.success("Database re-seeded!")
            st.session_state.portfolio = None
        else:
            st.error(r.stderr[:200])
    if st.button("Refresh Portfolio"):
        st.session_state.portfolio = None
        st.rerun()
    st.markdown("---")
    if st.session_state.screen != "dashboard":
        if st.button("← Dashboard"):
            st.session_state.screen = "dashboard"
            st.session_state.workflow_id = None
            st.session_state.workflow_state = None
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# SCREEN: DASHBOARD
# ──────────────────────────────────────────────────────────────────────────────
if st.session_state.screen == "dashboard":
    st.markdown("## Portfolio Dashboard")
    if not st.session_state.portfolio:
        with st.spinner("Loading customer portfolio..."):
            data = fetch_portfolio()
            if data:
                st.session_state.portfolio = data
            else:
                st.error("Cannot load portfolio. Is the FastAPI backend running on port 8000?")
                st.code("python -m uvicorn collection_assistant.api.main:app --port 8000")
                st.stop()

    def launch_pipeline(customer_id, account_id, trigger_context):
        with st.spinner("Starting analysis pipeline..."):
            try:
                wf_id = trigger_pipeline(customer_id, account_id, trigger_context)
                # Store the portfolio row for the customer banner
                row = next((r for r in st.session_state.portfolio if r["customer_id"]==customer_id), None)
                st.session_state.workflow_id = wf_id
                st.session_state.pipeline_row = row
                st.session_state.screen = "analysis"
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start pipeline: {e}")

    render_dashboard(st.session_state.portfolio, launch_pipeline)


# ──────────────────────────────────────────────────────────────────────────────
# SCREEN: ANALYSIS (pipeline execution + progressive results)
# ──────────────────────────────────────────────────────────────────────────────
elif st.session_state.screen == "analysis":
    wf_id   = st.session_state.workflow_id
    row     = st.session_state.get("pipeline_row") or {}
    trigger = st.session_state.get("dash_trigger", "routine_review")

    # ── Customer banner ──────────────────────────────────────────────────────
    name    = row.get("full_name", "Customer")
    cid     = row.get("customer_id", "")
    aid     = row.get("account_id", "")
    risk    = row.get("risk_segment", "medium")
    prod    = PRODUCT_LABELS.get(row.get("product_type",""), row.get("product_type",""))
    dpd     = row.get("days_past_due", 0)
    bal     = row.get("outstanding_balance", 0)
    rs      = RISK_STYLE.get(risk,"background:#eee;color:#333")
    dpd_clr = "#C62828" if dpd>60 else "#E65100" if dpd>30 else "#2E7D32"

    st.markdown(
        f'<div style="background:#fff;border:1px solid #E0E0E0;border-radius:8px;'
        f'padding:0.7rem 1.2rem;margin-bottom:0.8rem;display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap">'
        f'<div><div style="font-size:1.05rem;font-weight:700">{name}</div>'
        f'<div style="font-size:0.72rem;color:#888;font-family:monospace">{cid} · {aid}</div></div>'
        f'<span style="color:#DDD">|</span>'
        f'<span style="{rs};padding:3px 10px;border-radius:10px;font-size:0.73rem;font-weight:700">{risk.upper()} RISK</span>'
        f'<span style="color:#DDD">|</span>'
        f'<span style="font-size:0.85rem"><b>{prod}</b></span>'
        f'<span style="color:#DDD">|</span>'
        f'<span style="font-size:0.85rem">DPD: <b style="color:{dpd_clr}">{dpd}</b></span>'
        f'<span style="color:#DDD">|</span>'
        f'<span style="font-size:0.85rem">Balance: <b>${bal:,.0f}</b></span>'
        f'<span style="color:#DDD">|</span>'
        f'<span style="font-size:0.85rem">Trigger: <b>{trigger.replace("_"," ").title()}</b></span>'
        f'<span style="margin-left:auto;font-family:monospace;background:#F3E5F5;color:#4A148C;'
        f'padding:3px 10px;border-radius:8px;font-size:0.72rem;font-weight:700">{wf_id}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Poll workflow state ───────────────────────────────────────────────────
    state = get_workflow_state(wf_id) or {}
    agent_statuses = state.get("agent_statuses", {})
    workflow_status = state.get("workflow_status", "in_progress")

    # Compute progress %
    total_agents = 6
    done_count = sum(1 for v in agent_statuses.values() if v.get("status") == "completed")
    in_progress = any(v.get("status") == "running" for v in agent_statuses.values())
    progress_pct = min(int(done_count / total_agents * 95), 95) if workflow_status != "completed" else 100
    if workflow_status == "completed":
        progress_label = "Analysis complete"
    elif in_progress:
        running_names = [k.replace("_"," ").title() for k,v in agent_statuses.items() if v.get("status")=="running"]
        progress_label = f"Running: {', '.join(running_names)}…"
    else:
        progress_label = "Initialising pipeline…"

    # Progress bar
    bar_color = "#137333" if workflow_status=="completed" else "#A100FF"
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0.8rem;background:#fff;'
        f'border:1px solid #E0E0E0;border-radius:8px;padding:0.55rem 1.2rem;margin-bottom:0.8rem">'
        f'<span style="font-size:0.72rem;font-weight:600;color:#888;min-width:110px">Analysis Progress</span>'
        f'<div style="flex:1;height:6px;background:#EEE;border-radius:3px;overflow:hidden">'
        f'<div style="width:{progress_pct}%;height:100%;background:{bar_color};border-radius:3px;transition:width 0.4s ease"></div></div>'
        f'<span style="font-size:0.78rem;font-weight:700;color:{bar_color};min-width:32px">{progress_pct}%</span>'
        f'<span style="font-size:0.8rem;color:#888">{progress_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Two-column layout ────────────────────────────────────────────────────
    col_left, col_right = st.columns([1.4, 3], gap="medium")

    with col_left:
        render_execution_panel(agent_statuses)

    with col_right:
        # ── Summary zone (top): Complete banner + NBA ───────────────────────
        nba_done = (agent_statuses.get("nba", {}).get("status") == "completed"
                    and state.get("nba_recommendation"))
        audit_done = (agent_statuses.get("audit", {}).get("status") == "completed")

        if workflow_status == "completed":
            total_ms = state.get("total_ms", 0) or 0
            nba_rec = state.get("nba_recommendation") or {}
            nba_action = nba_rec.get("action", "—").replace("_"," ").title()
            nba_conf   = nba_rec.get("confidence_score", 0)
            st.markdown(
                f'<div style="background:linear-gradient(90deg,#1B5E20,#2E7D32);color:white;'
                f'border-radius:10px;padding:0.8rem 1.2rem;display:flex;align-items:center;'
                f'gap:1rem;margin-bottom:0.8rem;flex-wrap:wrap">'
                f'<span style="font-size:1.3rem">✅</span>'
                f'<div style="flex:1">'
                f'<div style="font-weight:700;font-size:0.95rem">Analysis Complete — All 6 agents executed successfully</div>'
                f'<div style="font-size:0.82rem;opacity:0.85;margin-top:2px">'
                f'NBA Recommendation: <b>{nba_action}</b> · Confidence: <b>{nba_conf:.0%}</b></div>'
                f'</div>'
                f'<span style="background:rgba(255,255,255,0.2);padding:4px 12px;border-radius:8px;'
                f'font-size:0.8rem;font-weight:600">{total_ms/1000:.1f}s total</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if nba_done:
            render_nba_card(state.get("nba_recommendation") or {})

        if nba_done or workflow_status == "completed":
            st.markdown(
                '<hr style="border:none;border-top:2px dashed #E8E8E8;margin:0.8rem 0 1rem">',
                unsafe_allow_html=True,
            )

        # ── Detail cards (progressively visible) ───────────────────────────
        cp_done  = agent_statuses.get("customer_profile", {}).get("status") == "completed"
        ap_done  = agent_statuses.get("account_profile",  {}).get("status") == "completed"
        arr_done = agent_statuses.get("arrears_prediction",{}).get("status") == "completed"
        dis_done = agent_statuses.get("dispute",           {}).get("status") == "completed"

        if cp_done or ap_done:
            c1, c2 = st.columns(2)
            with c1:
                if cp_done:
                    render_customer_card(state.get("customer_profile") or {})
                else:
                    st.markdown(
                        '<div style="border:2px dashed #E8E8E8;border-radius:10px;padding:2rem;'
                        'text-align:center;color:#ccc"><div style="font-size:2rem">👤</div>'
                        '<div style="margin-top:0.4rem;font-size:0.85rem">Customer Profile<br>Loading…</div></div>',
                        unsafe_allow_html=True)
            with c2:
                if ap_done:
                    render_account_card(state.get("account_profile") or {})
                else:
                    st.markdown(
                        '<div style="border:2px dashed #E8E8E8;border-radius:10px;padding:2rem;'
                        'text-align:center;color:#ccc"><div style="font-size:2rem">🏦</div>'
                        '<div style="margin-top:0.4rem;font-size:0.85rem">Account Profile<br>Loading…</div></div>',
                        unsafe_allow_html=True)

        if arr_done or dis_done:
            c3, c4 = st.columns(2)
            with c3:
                if arr_done:
                    current_dpd = (state.get("account_profile") or {}).get("days_past_due", 0)
                    render_arrears_card(state.get("arrears_prediction") or {}, current_dpd=current_dpd)
                else:
                    st.markdown(
                        '<div style="border:2px dashed #E8E8E8;border-radius:10px;padding:2rem;'
                        'text-align:center;color:#ccc"><div style="font-size:2rem">📊</div>'
                        '<div style="margin-top:0.4rem;font-size:0.85rem">Arrears Prediction<br>Loading…</div></div>',
                        unsafe_allow_html=True)
            with c4:
                if dis_done:
                    render_dispute_card(state.get("dispute_summary") or {})
                else:
                    st.markdown(
                        '<div style="border:2px dashed #E8E8E8;border-radius:10px;padding:2rem;'
                        'text-align:center;color:#ccc"><div style="font-size:2rem">⚖</div>'
                        '<div style="margin-top:0.4rem;font-size:0.85rem">Dispute Detection<br>Loading…</div></div>',
                        unsafe_allow_html=True)

        if not (cp_done or ap_done):
            st.markdown(
                '<div style="text-align:center;padding:3rem 2rem;color:#aaa">'
                '<div style="font-size:3rem;margin-bottom:0.8rem">⚙</div>'
                '<div style="font-size:1rem;font-weight:600">Pipeline Running</div>'
                '<div style="font-size:0.85rem;margin-top:0.3rem">Agent outputs appear here as each stage completes</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        # ── Audit Trail (bottom) ────────────────────────────────────────────
        if audit_done:
            render_audit_panel(state.get("audit_record") or {}, wf_id)

    # ── Keep polling until done ───────────────────────────────────────────────
    if workflow_status not in ("completed", "error"):
        time.sleep(1)
        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# SCREEN: RESULTS (legacy — kept as fallback redirect to analysis)
# ──────────────────────────────────────────────────────────────────────────────
elif st.session_state.screen == "results":
    st.session_state.screen = "analysis"
    st.rerun()
