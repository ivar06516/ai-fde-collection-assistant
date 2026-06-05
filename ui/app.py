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
    with open(css_path, encoding='utf-8') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown("""<style>
/* Hide all Streamlit chrome — toolbar, deploy, menu, footer */
[data-testid="stToolbar"]          { display: none !important; }
[data-testid="stDecoration"]       { display: none !important; }
[data-testid="stStatusWidget"]     { display: none !important; }
header[data-testid="stHeader"]     { display: none !important; }
#MainMenu                          { display: none !important; }
footer                             { display: none !important; }
.stDeployButton                    { display: none !important; }
/* Tighter top padding since header is hidden */
.block-container { padding-top: 1rem !important; }
/* Spinner animation */
@keyframes spin { to { transform: rotate(360deg); } }
</style>""", unsafe_allow_html=True)

# ── Imports ────────────────────────────────────────────────────────────────────
from ui.components.arrears_card import render_arrears_card
from ui.components.audit_panel import render_audit_panel
from ui.components.customer_profile_page import render_customer_profile_page
from ui.components.dashboard import render_dashboard
from ui.components.dispute_card import render_dispute_card
from ui.components.execution_panel import render_execution_panel
from ui.components.nba_card import render_nba_card
from ui.sse_client import (
    fetch_customer_detail, fetch_customer_runs, fetch_last_run,
    fetch_portfolio, get_workflow_state, trigger_pipeline,
)

PRODUCT_LABELS = {
    "personal_loan":"Personal Loan","credit_card":"Credit Card",
    "mortgage":"Mortgage","auto_loan":"Auto Loan","overdraft":"Overdraft",
}
RISK_STYLE = {
    "low":"background:#E8F5E9;color:#2E7D32","medium":"background:#FFF8E1;color:#E65100",
    "high":"background:#FFEBEE;color:#C62828","hardship":"background:#EDE7F6;color:#4527A0",
}

# ── Global header with page navigation ────────────────────────────────────────
def _render_header():
    page = st.session_state.get("page", "dashboard")
    row  = st.session_state.get("pipeline_row") or {}
    cid  = st.session_state.get("profile_customer_id", "")

    # Build breadcrumb
    crumbs = [("🏠 Dashboard", "dashboard")]
    if page == "analysis":
        name = row.get("full_name", "")
        crumbs.append((f"Analysis — {name}", "analysis"))
    elif page == "profile":
        portfolio = st.session_state.get("portfolio") or []
        prof_row  = next((r for r in portfolio if r["customer_id"] == cid), {})
        crumbs.append((f"Profile — {prof_row.get('full_name', cid)}", "profile"))

    crumb_html = ""
    for i, (label, target) in enumerate(crumbs):
        is_active = (target == page)
        sep = ' <span style="color:#555;margin:0 0.4rem">›</span> ' if i > 0 else ""
        color = "#FFFFFF" if is_active else "#999999"
        weight = "700" if is_active else "400"
        crumb_html += f'{sep}<span style="color:{color};font-weight:{weight};font-size:0.85rem">{label}</span>'

    st.markdown(
        f'<div style="background:#1A1A1A;padding:0.6rem 1.5rem;border-radius:8px;'
        f'margin-bottom:0.8rem;display:flex;align-items:center;gap:1.2rem">'
        f'<span style="color:#A100FF;font-size:1.15rem;font-weight:800;letter-spacing:-0.5px">Accenture</span>'
        f'<span style="color:#444;font-size:1rem">|</span>'
        f'<span style="color:#888;font-size:0.85rem">AI FDE Collection Assistant</span>'
        f'<span style="color:#444;margin:0 0.2rem">|</span>'
        f'<nav style="display:flex;align-items:center">{crumb_html}</nav>'
        f'</div>',
        unsafe_allow_html=True,
    )

_render_header()

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
    ("workflow_mode","live"),   # live | replay
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:

    # ── App Identity ────────────────────────────────────────────────────────
    st.markdown(
        '<div style="padding:0.5rem 0 0.8rem">'
        '<div style="color:#A100FF;font-size:1.1rem;font-weight:800;letter-spacing:-0.5px">Accenture</div>'
        '<div style="color:#888;font-size:0.75rem;margin-top:1px">AI FDE Collection Assistant</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # LLM provider badge
    provider = os.environ.get("LLM_PROVIDER", "free_cloud")
    provider_labels = {"free_cloud": "🟢 Groq (Free)", "local": "🟡 Ollama (Local)", "premium": "🟣 Anthropic"}
    provider_label = provider_labels.get(provider, provider)
    st.markdown(
        f'<div style="background:rgba(161,0,255,0.15);border:1px solid rgba(161,0,255,0.3);'
        f'border-radius:8px;padding:0.4rem 0.8rem;margin-bottom:0.8rem">'
        f'<div style="font-size:0.68rem;color:#888;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:0.05em;margin-bottom:2px">LLM Provider</div>'
        f'<div style="color:#E0C8FF;font-weight:700;font-size:0.85rem">{provider_label}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Navigation ──────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.68rem;color:#666;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.06em;margin-bottom:0.4rem">Navigation</div>',
        unsafe_allow_html=True,
    )

    cur_page = st.session_state.page
    portfolio = st.session_state.portfolio or []

    # Dashboard link
    dash_style = ("background:linear-gradient(135deg,#A100FF,#7B00CC);color:white;border:none;"
                  if cur_page == "dashboard"
                  else "background:#2D2D2D;color:#CCC;border:1px solid #444;")
    if st.button("🏠  Dashboard", use_container_width=True,
                 type="primary" if cur_page == "dashboard" else "secondary"):
        st.session_state.page = "dashboard"
        st.session_state.dash_selected = None
        st.rerun()

    # Analysis page link (only if an active or replay workflow exists)
    if st.session_state.workflow_id:
        row = st.session_state.get("pipeline_row") or {}
        cust_name = row.get("full_name", "Analysis")
        label = f"📊  Analysis"
        if st.button(label, use_container_width=True,
                     type="primary" if cur_page == "analysis" else "secondary"):
            st.session_state.page = "analysis"
            st.rerun()
        if cust_name and cur_page == "analysis":
            st.markdown(
                f'<div style="font-size:0.72rem;color:#888;padding:1px 8px;'
                f'margin-bottom:4px">↳ {cust_name}</div>',
                unsafe_allow_html=True,
            )

    # Customer Profile link (only if one is loaded)
    if st.session_state.profile_customer_id:
        prof_row = next((r for r in portfolio if r["customer_id"] == st.session_state.profile_customer_id), {})
        prof_name = prof_row.get("full_name", st.session_state.profile_customer_id)
        if st.button("👤  Customer Profile", use_container_width=True,
                     type="primary" if cur_page == "profile" else "secondary"):
            st.session_state.page = "profile"
            st.rerun()
        if cur_page == "profile":
            st.markdown(
                f'<div style="font-size:0.72rem;color:#888;padding:1px 8px;'
                f'margin-bottom:4px">↳ {prof_name}</div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="border-top:1px solid #333;margin:0.8rem 0"></div>',
                unsafe_allow_html=True)

    # ── Data Management ─────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.68rem;color:#666;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.06em;margin-bottom:0.4rem">Data Management</div>',
        unsafe_allow_html=True,
    )
    if st.button("🔄  Refresh Portfolio", use_container_width=True):
        st.session_state.portfolio = None
        st.rerun()
    if st.button("🌱  Seed Database", use_container_width=True):
        import subprocess
        r = subprocess.run(
            [sys.executable, "scripts/seed_db.py", "--reset"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if r.returncode == 0:
            st.success("Database re-seeded!")
            st.session_state.portfolio = None
        else:
            st.error(r.stderr[:200])


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


# ── Module-level navigation helpers (accessible from all page blocks) ──────────
def go_to_replay(workflow_id: str, full_state: dict, customer_id: str):
    """Load a past run from DB into the analysis screen without running the pipeline.

    workflow_audit excludes agent_statuses when saved, so we inject synthetic
    completed statuses so the left pipeline panel and right cards all render correctly.
    """
    row = next((r for r in (st.session_state.portfolio or []) if r["customer_id"] == customer_id), {})

    # Inject synthetic completed agent statuses (not stored in DB)
    _STAGE_MAP = {
        "customer_profile":   1, "account_profile":    1,
        "arrears_prediction": 2, "dispute":            2,
        "nba":                3, "audit":              3,
    }
    if not full_state.get("agent_statuses"):
        full_state["agent_statuses"] = {
            name: {"stage": stage, "status": "completed",
                   "elapsed_ms": None, "error": None,
                   "started_at": None, "completed_at": None}
            for name, stage in _STAGE_MAP.items()
        }
    # Ensure workflow is marked completed
    full_state["workflow_status"] = "completed"

    st.session_state.workflow_id = workflow_id
    st.session_state.workflow_state = full_state
    st.session_state.pipeline_row = row
    st.session_state.workflow_mode = "replay"
    st.session_state.page = "analysis"
    st.rerun()


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
                st.session_state.workflow_mode = "live"
                st.session_state.page = "analysis"
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start pipeline: {e}")

    def go_to_profile(customer_id):
        st.session_state.profile_customer_id = customer_id
        st.session_state.profile_detail = None
        st.session_state.page = "profile"
        st.rerun()



    def _view_run_from_dashboard(wf_id, cid):
        """Fetch full state for a specific workflow run and load it."""
        import httpx as _httpx
        from collection_assistant.config import get_settings as _gs
        try:
            settings = _gs()
            resp = _httpx.get(f"{settings.streamlit_api_url}/collections/{wf_id}/audit", timeout=8)
            if resp.status_code == 200:
                full_state = resp.json().get("full_state") or {}
                go_to_replay(wf_id, full_state, cid)
            else:
                st.error(f"Could not load run {wf_id}")
        except Exception as e:
            st.error(f"Error: {e}")

    render_dashboard(st.session_state.portfolio, go_to_analysis,
                     on_view_customer=go_to_profile,
                     on_view_run=_view_run_from_dashboard)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "analysis":
    wf_id   = st.session_state.workflow_id
    row     = st.session_state.get("pipeline_row") or {}

    # Back button (breadcrumb already in header)
    _, bc2 = st.columns([6, 1])
    with bc2:
        if st.button("← Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()

    # Customer banner
    _customer_banner(row, wf_id)

    # State: live pipeline polls API; replay loads stored state from session
    if st.session_state.get("workflow_mode") == "replay":
        state = st.session_state.get("workflow_state") or {}
    else:
        state = get_workflow_state(wf_id) or {}
    agent_statuses = state.get("agent_statuses", {})
    workflow_status = state.get("workflow_status", "in_progress")

    # Progress bar
    done_count  = sum(1 for v in agent_statuses.values() if v.get("status")=="completed")
    in_run      = any(v.get("status")=="running" for v in agent_statuses.values())
    progress_pct = 100 if workflow_status=="completed" else min(int(done_count/6*95), 95)
    bar_color    = "#137333" if workflow_status=="completed" else "#A100FF"
    if workflow_status=="completed":
        prog_label = "Replaying stored result" if st.session_state.get('workflow_mode') == 'replay' else "Analysis complete"
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
        nba_done  = (agent_statuses.get("nba",{}).get("status")=="completed" and state.get("nba_recommendation"))
        arr_done  = agent_statuses.get("arrears_prediction",{}).get("status") == "completed"
        dis_done  = agent_statuses.get("dispute",{}).get("status") == "completed"
        audit_done= agent_statuses.get("audit",{}).get("status") == "completed"
        any_done  = nba_done or arr_done or dis_done

        def _placeholder(icon, label):
            st.markdown(
                f'<div style="border:2px dashed #E8E8E8;border-radius:10px;padding:1.5rem;'
                f'text-align:center;color:#ccc"><div style="font-size:1.6rem">{icon}</div>'
                f'<div style="margin-top:0.3rem;font-size:0.8rem">{label}<br>Loading…</div></div>',
                unsafe_allow_html=True)

        if not any_done:
            st.markdown(
                '<div style="text-align:center;padding:3rem;color:#aaa">'
                '<div style="font-size:3rem">⚙</div>'
                '<div style="font-size:1rem;font-weight:600;margin-top:0.5rem">Pipeline Running</div>'
                '<div style="font-size:0.85rem;margin-top:0.3rem">Results appear below as each stage completes</div>'
                '</div>', unsafe_allow_html=True)
        else:
            # ── Complete banner (always visible, compact) ─────────────────
            if workflow_status == "completed":
                nba_rec  = state.get("nba_recommendation") or {}
                total_ms = state.get("total_ms", 0) or 0
                st.markdown(
                    f'<div style="background:linear-gradient(90deg,#1B5E20,#2E7D32);color:white;'
                    f'border-radius:8px;padding:0.55rem 1rem;display:flex;align-items:center;'
                    f'gap:0.8rem;margin-bottom:0.6rem">'
                    f'<span>✅</span>'
                    f'<span style="flex:1;font-weight:700;font-size:0.88rem">Analysis Complete</span>'
                    f'<span style="font-size:0.8rem;opacity:0.9">'
                    f'NBA: <b>{nba_rec.get("action","—").replace("_"," ").title()}</b>'
                    f' · <b>{nba_rec.get("confidence_score",0):.0%}</b></span>'
                    f'<span style="background:rgba(255,255,255,0.2);padding:2px 10px;border-radius:6px;'
                    f'font-size:0.75rem;font-weight:600">{total_ms/1000:.1f}s</span></div>',
                    unsafe_allow_html=True,
                )

            # ── Tabs: one click to any output, zero scroll ────────────────
            tab_nba_label  = "⭐ NBA" + (" ✓" if nba_done  else " ⟳")
            tab_pred_label = "📊 Predictions" + (" ✓" if arr_done and dis_done else " ⟳")
            tab_audit_label= "📋 Audit Trail" + (" ✓" if audit_done else " ⟳")

            t1, t2, t3 = st.tabs([tab_nba_label, tab_pred_label, tab_audit_label])

            with t1:
                if nba_done:
                    render_nba_card(state.get("nba_recommendation") or {})
                else:
                    _placeholder("⭐", "Next Best Action — waiting for Stage 3")

            with t2:
                if arr_done or dis_done:
                    p1, p2 = st.columns(2, gap="medium")
                    with p1:
                        if arr_done:
                            dpd_now = (state.get("account_profile") or {}).get("days_past_due", 0)
                            render_arrears_card(state.get("arrears_prediction") or {}, current_dpd=dpd_now)
                        else:
                            _placeholder("📊", "Arrears Prediction — waiting for Stage 2")
                    with p2:
                        if dis_done:
                            render_dispute_card(state.get("dispute_summary") or {})
                        else:
                            _placeholder("⚖", "Dispute Detection — waiting for Stage 2")
                else:
                    _placeholder("📊", "Predictions — waiting for Stage 2")

            with t3:
                if audit_done:
                    render_audit_panel(state.get("audit_record") or {}, wf_id)
                else:
                    _placeholder("📋", "Audit Trail — waiting for pipeline to complete")

    # Keep polling — skip when replaying a stored result
    if st.session_state.get("workflow_mode") != "replay" and workflow_status not in ("completed","error"):
        time.sleep(1)
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — CUSTOMER PROFILE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "profile":
    # Back button (breadcrumb already in header)
    _, bc2 = st.columns([5, 1])
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

    # Load run history for this customer
    from ui.sse_client import fetch_customer_runs as _fetch_runs
    profile_runs = _fetch_runs(cid)

    def go_to_replay_from_profile(wf_id, customer_id):
        """Fetch audit record for any run and load it into the analysis screen."""
        import httpx as _httpx
        from collection_assistant.config import get_settings as _gs
        try:
            settings = _gs()
            resp = _httpx.get(f"{settings.streamlit_api_url}/collections/{wf_id}/audit", timeout=8)
            if resp.status_code == 200:
                full_state = resp.json().get("full_state") or {}
                # go_to_replay injects synthetic agent_statuses if missing
                go_to_replay(wf_id, full_state, customer_id)
            else:
                st.error(f"Could not load run {wf_id}")
        except Exception as e:
            st.error(f"Error loading run: {e}")

    render_customer_profile_page(detail, go_to_analysis_from_profile,
                                  runs=profile_runs, on_view_run=go_to_replay_from_profile)
