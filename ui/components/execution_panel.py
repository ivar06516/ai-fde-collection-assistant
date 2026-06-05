"""Pipeline execution panel — left column of the analysis screen."""
import streamlit as st

AGENT_CONFIG = {
    "customer_profile":   {"stage": "Stage 1", "icon": "👤", "label": "Customer Profile",   "model": "Groq 70B"},
    "account_profile":    {"stage": "Stage 1", "icon": "🏦", "label": "Account Profile",    "model": "Groq 70B"},
    "arrears_prediction": {"stage": "Stage 2", "icon": "📊", "label": "Arrears Prediction", "model": "Groq 70B"},
    "dispute":            {"stage": "Stage 2", "icon": "⚖",  "label": "Dispute Detection",  "model": "Groq 70B"},
    "nba":                {"stage": "Stage 3", "icon": "⭐", "label": "Next Best Action",    "model": "Groq 70B"},
    "audit":              {"stage": "Stage 3", "icon": "📋", "label": "Audit Trail",         "model": "Groq 8B"},
}

STATUS_CSS = {
    "waiting":   ("background:#FAFAFA;border:1.5px solid #E8E8E8",   "⏳", "#888"),
    "running":   ("background:#FFF8E1;border:1.5px solid #E65100;border-left:3px solid #E65100", "⟳", "#E65100"),
    "completed": ("background:#F1F8F1;border:1.5px solid #2E7D32;border-left:3px solid #2E7D32", "✅", "#2E7D32"),
    "error":     ("background:#FFF5F5;border:1.5px solid #C62828;border-left:3px solid #C62828", "❌", "#C62828"),
    "unknown":   ("background:#FAFAFA;border:1.5px solid #E8E8E8",   "⏳", "#888"),
}

STAGE_GROUPS = [
    ("Stage 1 — Parallel", ["customer_profile", "account_profile"]),
    ("Stage 2 — Parallel", ["arrears_prediction", "dispute"]),
    ("Stage 3 — Sequential", ["nba", "audit"]),
]


def _agent_node(agent_key: str, status_info: dict) -> str:
    cfg = AGENT_CONFIG.get(agent_key, {"stage": "?", "icon": "🤖", "label": agent_key, "model": ""})
    status = status_info.get("status", "waiting")
    box_style, icon, color = STATUS_CSS.get(status, STATUS_CSS["waiting"])
    elapsed_ms = status_info.get("elapsed_ms")
    elapsed = f"{elapsed_ms/1000:.1f}s" if elapsed_ms else ""
    error = status_info.get("error", "")
    spinner_html = (
        '<span style="display:inline-block;width:14px;height:14px;border:2px solid #E65100;'
        'border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;'
        'vertical-align:middle;margin-top:1px"></span>'
        if status == "running" else icon
    )
    return (
        f'<div style="{box_style};border-radius:8px;padding:0.55rem 0.7rem;'
        f'margin-bottom:0.35rem;display:flex;align-items:flex-start;gap:0.6rem">'
        f'<div style="font-size:1rem;min-width:20px;text-align:center;margin-top:1px">{cfg["icon"]}</div>'
        f'<div style="flex:1">'
        f'<div style="font-size:0.84rem;font-weight:600">{cfg["label"]}</div>'
        f'<div style="font-size:0.75rem;color:#999">{cfg["stage"]} · {cfg["model"]}</div>'
        + (f'<div style="font-size:0.75rem;color:#137333;font-weight:600;margin-top:2px">{elapsed}</div>' if elapsed else "")
        + (f'<div style="font-size:0.75rem;color:#C62828;margin-top:2px">{error[:60]}</div>' if error and status == "error" else "")
        + f'</div>'
        f'<div style="font-size:0.9rem;margin-top:2px">{spinner_html}</div>'
        f'</div>'
    )


def _timeline_bars(agent_statuses: dict) -> str:
    max_ms = max((v.get("elapsed_ms") or 0 for v in agent_statuses.values()), default=1) or 1
    rows = ""
    for key, cfg in AGENT_CONFIG.items():
        info = agent_statuses.get(key, {})
        ms = info.get("elapsed_ms") or 0
        pct = int(ms / max_ms * 100) if max_ms else 0
        ms_str = f"{ms:,}ms" if ms else "—"
        rows += (
            f'<div style="display:flex;align-items:center;gap:0.4rem;margin-bottom:0.25rem">'
            f'<span style="font-size:0.75rem;color:#616161;min-width:80px;white-space:nowrap">{cfg["label"][:14]}</span>'
            f'<div style="flex:1;height:7px;background:#EEE;border-radius:4px;overflow:hidden">'
            f'<div style="width:{pct}%;height:100%;background:#A100FF;border-radius:4px;transition:width 0.4s ease"></div></div>'
            f'<span style="font-size:0.67rem;color:#616161;min-width:44px;text-align:right">{ms_str}</span>'
            f'</div>'
        )
    return rows


def render_execution_panel(agent_statuses: dict) -> None:
    """Render the left-column pipeline panel."""
    st.markdown(
        '<div style="font-size:0.75rem;font-weight:700;color:#616161;text-transform:uppercase;'
        'letter-spacing:0.06em;margin-bottom:0.8rem">Agent Execution Pipeline</div>',
        unsafe_allow_html=True,
    )

    for stage_label, agent_keys in STAGE_GROUPS:
        STAGE_TOOLTIPS = {
            "Stage 1 — Parallel":    "Customer Profile + Account Profile run simultaneously",
            "Stage 2 — Parallel":    "Arrears Prediction + Dispute Detection run simultaneously",
            "Stage 3 — Sequential":  "Next Best Action → Audit Trail run in order",
        }
        tip = STAGE_TOOLTIPS.get(stage_label, "")
        st.markdown(
            f'<div title="{tip}" style="background:#F3E5F5;color:#4A148C;font-size:0.75rem;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.05em;padding:2px 8px;border-radius:4px;'
            f'display:inline-block;margin-bottom:0.4rem;cursor:help;border-bottom:1px dashed #9b59b6">{stage_label}</div>',
            unsafe_allow_html=True,
        )
        nodes_html = "".join(_agent_node(k, agent_statuses.get(k, {})) for k in agent_keys)
        st.markdown(nodes_html, unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center;color:#CCC;margin:0.25rem 0;font-size:1rem;line-height:1">↓</div>',
            unsafe_allow_html=True,
        )

    # Elapsed timeline
    completed_any = any(
        (v.get("elapsed_ms") or 0) > 0 for v in agent_statuses.values()
    )
    if completed_any:
        st.markdown(
            '<div style="margin-top:0.8rem;padding-top:0.8rem;border-top:1px solid #EEE">'
            '<div style="font-size:0.75rem;color:#616161;font-weight:700;text-transform:uppercase;'
            'letter-spacing:0.05em;margin-bottom:0.4rem">Elapsed Time</div>'
            + _timeline_bars(agent_statuses)
            + '</div>',
            unsafe_allow_html=True,
        )
