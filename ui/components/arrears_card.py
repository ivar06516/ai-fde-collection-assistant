"""Arrears Prediction card with Plotly charts."""
import plotly.graph_objects as go
import streamlit as st

TRAJECTORY_COLORS = {
    "improving": "#00B050", "stable": "#FFA500",
    "deteriorating": "#E30000", "critical": "#7B00CC",
}


def _gauge_chart(value: float) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value * 100,
        title={"text": "Default Probability %"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#A100FF"},
            "steps": [
                {"range": [0, 30], "color": "#E6F4EA"},
                {"range": [30, 60], "color": "#FFF3E0"},
                {"range": [60, 100], "color": "#FCE8E6"},
            ],
        },
    ))
    fig.update_layout(height=220, margin=dict(l=10, r=10, t=30, b=10))
    return fig


def _dpd_forecast_chart(current: int, d30: int, d60: int, d90: int) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=["Now", "+30 days", "+60 days", "+90 days"],
        y=[current, d30, d60, d90],
        mode="lines+markers",
        line={"color": "#A100FF", "width": 3},
        marker={"size": 10},
        fill="tozeroy",
        fillcolor="rgba(161,0,255,0.08)",
    ))
    fig.update_layout(
        title="DPD Forecast", height=220,
        yaxis_title="Days Past Due", margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def _risk_factors_bar_chart(factors: list) -> go.Figure:
    """Horizontal bar chart for ranked risk factors (AC-004-08)."""
    if not factors:
        return go.Figure()
    # Accept both dict {"name": str, "weight": float} and legacy str items
    names, weights = [], []
    for f in factors[:6]:
        if isinstance(f, dict):
            names.append(f.get("name", str(f))[:45])
            weights.append(f.get("weight", 0.5))
        else:
            names.append(str(f)[:45])
            weights.append(0.5)

    bar_colors = ["#E30000" if w >= 0.7 else "#FFA500" if w >= 0.45 else "#A100FF" for w in weights]
    fig = go.Figure(go.Bar(
        x=weights,
        y=names,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{w:.0%}" for w in weights],
        textposition="outside",
    ))
    fig.update_layout(
        title="Risk Factor Weights",
        xaxis={"range": [0, 1.1], "tickformat": ".0%", "title": "Weight"},
        yaxis={"autorange": "reversed"},
        height=max(180, len(names) * 38),
        margin=dict(l=10, r=50, t=40, b=10),
    )
    return fig


def render_arrears_card(prediction: dict) -> None:
    st.markdown("### 📊 Arrears Prediction")
    if not prediction:
        st.warning("No arrears prediction data")
        return
    trajectory = prediction.get("arrears_trajectory", "stable")
    traj_color = TRAJECTORY_COLORS.get(trajectory, "#666")
    st.markdown(
        f'<span style="background:{traj_color};color:white;padding:3px 10px;'
        f'border-radius:12px;font-size:0.85rem;font-weight:700">'
        f'{trajectory.upper()}</span>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Arrears Band", prediction.get("current_arrears_band", "-"))
        st.metric("Confidence", f"{prediction.get('confidence_score', 0):.0%}")
    with col2:
        st.metric("Pred. Arrears", f"${prediction.get('predicted_arrears_amount', 0):,.2f}")
        st.metric("DPD @90d", prediction.get("predicted_dpd_90", 0))

    tab1, tab2, tab3 = st.tabs(["Default Probability", "DPD Forecast", "Risk Factors"])
    with tab1:
        st.plotly_chart(
            _gauge_chart(prediction.get("default_probability", 0)),
            use_container_width=True,
        )
    with tab2:
        current_dpd = max(0, prediction.get("predicted_dpd_30", 0) - 10)
        st.plotly_chart(
            _dpd_forecast_chart(
                current_dpd,
                prediction.get("predicted_dpd_30", 0),
                prediction.get("predicted_dpd_60", 0),
                prediction.get("predicted_dpd_90", 0),
            ),
            use_container_width=True,
        )
    with tab3:
        factors = prediction.get("contributing_risk_factors", [])
        if factors:
            st.plotly_chart(_risk_factors_bar_chart(factors), use_container_width=True)
        else:
            st.info("No significant risk factors identified")

    if prediction.get("summary"):
        with st.expander("Prediction Summary"):
            st.write(prediction["summary"])
