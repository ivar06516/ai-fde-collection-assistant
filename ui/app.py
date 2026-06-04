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

from ui.components.arrears_card import render_arrears_card
from ui.components.account_card import render_account_card
from ui.components.audit_panel import render_audit_panel
from ui.components.customer_card import render_customer_card
from ui.components.dashboard import render_dashboard
from ui.components.dispute_card import render_dispute_card
from ui.components.execution_panel import render_execution_panel
from ui.components.nba_card import render_nba_card
from ui.sse_client import (
    fetch_portfolio, get_workflow_state, trigger_pipeline,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """<div class="fde-header" style="background:#1A1A1A;padding:0.7rem 1.5rem;
    border-radius:8px;margin-bottom:1rem;display:flex;align-items:center;gap:1rem">
    <span style="color:#A100FF;font-size:1.2rem;font-weight:800">Accenture</span>
    <span style="color:#555">|</span>
    <span style="color:#ccc;font-size:0.95rem">AI FDE Collection Assistant</span>
    </div>""",
    unsafe_allow_html=True,
)

# ── Session state init ─────────────────────────────────────────────────────────
for k, v in [("screen", "dashboard"), ("workflow_id", None),
             ("workflow_state", None), ("dash_selected", None),
             ("portfolio", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### FDE Collection Assistant")
    st.caption("Multi-Agent Architecture PoC")
    st.markdown("---")
    provider = os.environ.get("LLM_PROVIDER", "free_cloud")
    icons = {"free_cloud": "🟢 Groq (Free)", "local": "🟡 Ollama", "premium": "🟣 Anthropic"}
    st.info(f"LLM: **{icons.get(provider, provider)}**")
    st.markdown("---")
    if st.button("Seed Database", help="Re-seed all synthetic data"):
        import subprocess
        r = subprocess.run(
            [sys.executable, "scripts/seed_db.py", "--reset"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if r.returncode == 0:
            st.success("Database re-seeded!")
            st.session_state.portfolio = None  # force reload
        else:
            st.error(r.stderr[:200])
    if st.button("Refresh Portfolio"):
        st.session_state.portfolio = None
        st.rerun()
    st.markdown("---")
    if st.session_state.screen != "dashboard":
        if st.button("Dashboard"):
            st.session_state.screen = "dashboard"
            st.session_state.workflow_id = None
            st.session_state.workflow_state = None
            st.rerun()


# ── SCREEN: DASHBOARD ──────────────────────────────────────────────────────────
if st.session_state.screen == "dashboard":
    st.markdown("## Portfolio Dashboard")

    # Load portfolio (cached in session_state until refresh)
    if not st.session_state.portfolio:
        with st.spinner("Loading customer portfolio..."):
            data = fetch_portfolio()
            if data:
                st.session_state.portfolio = data
            else:
                st.error("Could not load portfolio. Is the FastAPI backend running on port 8000?")
                st.code("python -m uvicorn collection_assistant.api.main:app --port 8000")
                st.stop()

    def launch_pipeline(customer_id, account_id, trigger_context):
        with st.spinner("Starting analysis pipeline..."):
            try:
                wf_id = trigger_pipeline(customer_id, account_id, trigger_context)
                st.session_state.workflow_id = wf_id
                st.session_state.pipeline_customer = customer_id
                st.session_state.pipeline_account = account_id
                st.session_state.screen = "executing"
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start pipeline: {e}")

    render_dashboard(st.session_state.portfolio, launch_pipeline)


# ── SCREEN: EXECUTING ─────────────────────────────────────────────────────────
elif st.session_state.screen == "executing":
    wf_id = st.session_state.workflow_id
    cust  = st.session_state.get("pipeline_customer", "")
    acc   = st.session_state.get("pipeline_account", "")

    st.markdown("## Pipeline Executing")
    col_info, col_back = st.columns([4, 1])
    with col_info:
        st.markdown(
            f'<span style="font-family:monospace;background:#F3E5F5;color:#4A148C;'
            f'padding:3px 10px;border-radius:8px">{wf_id}</span> &nbsp; '
            f'Customer: <b>{cust}</b> · Account: <b>{acc}</b>',
            unsafe_allow_html=True)
    with col_back:
        if st.button("← Dashboard"):
            st.session_state.screen = "dashboard"
            st.rerun()

    ph = st.empty()
    with st.spinner("Running multi-agent pipeline..."):
        for _ in range(120):
            state = get_workflow_state(wf_id)
            if state:
                with ph.container():
                    render_execution_panel(state.get("agent_statuses", {}))
                if state.get("workflow_status") in ("completed", "error"):
                    st.session_state.workflow_state = state
                    st.session_state.screen = "results"
                    st.rerun()
            time.sleep(1)
        st.error("Pipeline timed out. Check API server logs.")


# ── SCREEN: RESULTS ───────────────────────────────────────────────────────────
elif st.session_state.screen == "results":
    wf_id  = st.session_state.workflow_id
    state  = st.session_state.workflow_state or {}
    total_ms = state.get("total_ms")
    ws = state.get("workflow_status", "")
    ws_color = "#137333" if ws == "completed" else "#C62828"

    # Header
    col_hdr, col_back = st.columns([5, 1])
    with col_hdr:
        st.markdown(
            f'## Analysis '
            f'<span style="background:{ws_color}1A;color:{ws_color};padding:3px 12px;'
            f'border-radius:10px;font-size:0.9rem;font-weight:700">'
            f'{ws.upper()}</span>',
            unsafe_allow_html=True)
        if total_ms:
            st.caption(f"Workflow `{wf_id}` completed in {total_ms:,}ms")
    with col_back:
        if st.button("← Dashboard", type="primary"):
            st.session_state.screen = "dashboard"
            st.session_state.workflow_id = None
            st.session_state.workflow_state = None
            st.rerun()

    # Results error banner
    errors = state.get("error_log", [])
    if errors:
        with st.expander(f"⚠ {len(errors)} agent error(s)", expanded=False):
            for e in errors:
                st.error(e)

    st.markdown("---")

    # Stage 1 + 2 — 2x2 grid
    c1, c2 = st.columns(2)
    with c1:
        render_customer_card(state.get("customer_profile") or {})
    with c2:
        render_account_card(state.get("account_profile") or {})

    c3, c4 = st.columns(2)
    with c3:
        current_dpd = (state.get("account_profile") or {}).get("days_past_due", 0)
        render_arrears_card(state.get("arrears_prediction") or {}, current_dpd=current_dpd)
    with c4:
        render_dispute_card(state.get("dispute_summary") or {})

    st.markdown("---")

    # Stage 3 — NBA
    render_nba_card(state.get("nba_recommendation") or {})

    # Audit trail
    render_audit_panel(state.get("audit_record") or {}, wf_id)
