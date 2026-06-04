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
    initial_sidebar_state="expanded",
)

css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from ui.components.account_card import render_account_card
from ui.components.arrears_card import render_arrears_card
from ui.components.audit_panel import render_audit_panel
from ui.components.customer_card import render_customer_card
from ui.components.dispute_card import render_dispute_card
from ui.components.execution_panel import render_execution_panel
from ui.components.nba_card import render_nba_card
from ui.sse_client import fetch_accounts, fetch_customers, get_workflow_state, trigger_pipeline

st.markdown(
    """<div class="fde-header">
    <div class="fde-logo-text">Accenture</div>
    <div style="font-size:1.1rem;color:#ccc">|</div>
    <div style="font-size:1rem;color:white">AI FDE Collection Assistant</div>
    </div>""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### FDE Collection Assistant")
    st.caption("Multi-Agent Architecture PoC")
    st.markdown("---")
    provider = os.environ.get("LLM_PROVIDER", "free_cloud")
    icons = {"free_cloud": "Groq (Free)", "local": "Ollama (Local)", "premium": "Anthropic (future)"}
    st.info(f"LLM: **{icons.get(provider, provider)}**")
    st.markdown("---")
    st.markdown("**Data Management**")
    if st.button("Seed Database"):
        import subprocess
        r = subprocess.run(
            [sys.executable, "scripts/seed_db.py"], capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if r.returncode == 0:
            st.success("Database seeded!")
        else:
            st.error(r.stderr[:200])

for k, v in [("workflow_id", None), ("workflow_state", None), ("screen", "input")]:
    if k not in st.session_state:
        st.session_state[k] = v

# --- SCREEN 1: INPUT ---
if st.session_state.screen == "input":
    st.markdown("## Run Collection Analysis")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### Customer & Account Selection")
        customers = fetch_customers()
        accounts = fetch_accounts()
        if customers:
            cmap = {c["label"]: c["id"] for c in customers}
            customer_id = cmap[st.selectbox("Customer", list(cmap.keys()))]
        else:
            customer_id = st.text_input("Customer ID", placeholder="CUST-001")
        if accounts:
            amap = {a["label"]: a["id"] for a in accounts}
            account_id = amap[st.selectbox("Account", list(amap.keys()))]
        else:
            account_id = st.text_input("Account ID", placeholder="ACC-001")
        trigger_context = st.selectbox("Trigger Context", [
            "routine_review", "missed_payment", "hardship_claim",
            "dispute_raised", "payment_arrangement_review", "legal_referral_review",
        ])
    with col2:
        st.markdown("### Quick Load Scenarios")
        scenarios = {
            "James Chen (Low Risk)": ("CUST-001", "ACC-001"),
            "Sarah Jones (Hold)": ("CUST-002", "ACC-002"),
            "Michael Okonkwo (Critical)": ("CUST-003", "ACC-003"),
            "Emma Patel (Hardship)": ("CUST-004", "ACC-004"),
            "David Brown (Dispute)": ("CUST-007", "ACC-007"),
        }
        for label, (cid, aid) in scenarios.items():
            if st.button(label, use_container_width=True):
                st.session_state.q_cid = cid
                st.session_state.q_aid = aid
                st.rerun()
        if "q_cid" in st.session_state:
            customer_id = st.session_state.q_cid
            account_id = st.session_state.q_aid
    st.markdown("---")
    if st.button("Run Analysis", type="primary", use_container_width=True):
        if not customer_id or not account_id:
            st.error("Please select a Customer ID and Account ID")
        else:
            with st.spinner("Starting pipeline..."):
                try:
                    wf_id = trigger_pipeline(customer_id, account_id, trigger_context)
                    st.session_state.workflow_id = wf_id
                    st.session_state.pipeline_customer = customer_id
                    st.session_state.pipeline_account = account_id
                    st.session_state.screen = "executing"
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to start pipeline: {e}")

# --- SCREEN 2: EXECUTING ---
elif st.session_state.screen == "executing":
    wf_id = st.session_state.workflow_id
    st.markdown(f"## Pipeline Executing")
    st.caption(f"Workflow ID: {wf_id}")
    ph = st.empty()
    with st.spinner("Running multi-agent pipeline..."):
        for _ in range(90):
            state = get_workflow_state(wf_id)
            if state:
                with ph.container():
                    render_execution_panel(state.get("agent_statuses", {}))
                if state.get("workflow_status") in ("completed", "error"):
                    st.session_state.workflow_state = state
                    st.session_state.screen = "results"
                    st.rerun()
            time.sleep(1)
        st.error("Pipeline timed out.")

# --- SCREEN 3: RESULTS ---
elif st.session_state.screen == "results":
    wf_id = st.session_state.workflow_id
    state = st.session_state.workflow_state or {}
    total_ms = state.get("total_ms")
    st.markdown("## Analysis Complete")
    if total_ms:
        st.caption(f"Workflow completed in {total_ms}ms")
    if st.button("New Analysis"):
        st.session_state.update({"screen": "input", "workflow_id": None, "workflow_state": None})
        st.rerun()
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        render_customer_card(state.get("customer_profile") or {})
    with c2:
        render_account_card(state.get("account_profile") or {})
    c3, c4 = st.columns(2)
    with c3:
        render_arrears_card(state.get("arrears_prediction") or {}, current_dpd=(state.get("account_profile") or {}).get("days_past_due", 0))
    with c4:
        render_dispute_card(state.get("dispute_summary") or {})
    st.markdown("---")
    render_nba_card(state.get("nba_recommendation") or {})
    render_audit_panel(state.get("audit_record") or {}, wf_id)
