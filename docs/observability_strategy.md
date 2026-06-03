# Observability Strategy — AI FDE Collection Assistant

## 1. Overview

Observability answers the question: **"What is the system doing and why?"** This strategy covers the three pillars — Metrics, Logs, and Traces — all fed into **Grafana Cloud (free tier)** via OpenTelemetry (already a project dependency).

**Platform:** Grafana Cloud free tier
- 10,000 Prometheus active series
- 50 GB Loki log ingestion/month
- 50 GB Tempo trace ingestion/month
- 14-day data retention
- Full Grafana dashboards + alerting

**Instrumentation library:** `opentelemetry-sdk` + `opentelemetry-exporter-otlp` (already in `pyproject.toml`)

---

## 2. The Three Pillars

```
Metrics  ──────────────────► Grafana Cloud Prometheus   ◄── What happened (numbers)
Logs     ──────────────────► Grafana Cloud Loki          ◄── Why it happened (text)
Traces   ──────────────────► Grafana Cloud Tempo         ◄── How it happened (flow)
                    ▲
                    │
         OpenTelemetry Collector
         (OTLP exporter in FastAPI)
```

---

## 3. Pillar 1 — Metrics (Prometheus via Grafana Cloud)

### 3.1 What We Measure

Every meaningful event in the pipeline is measured with a metric.

| Metric Name | Type | Labels | What It Tracks |
|---|---|---|---|
| `collection_workflow_total` | Counter | `status`, `trigger_context` | Total workflow runs by outcome |
| `collection_workflow_duration_seconds` | Histogram | `trigger_context` | End-to-end pipeline duration |
| `agent_execution_duration_seconds` | Histogram | `agent_name`, `stage` | Per-agent latency |
| `agent_execution_total` | Counter | `agent_name`, `status` | Agent runs by success/failure |
| `llm_tokens_used_total` | Counter | `agent_name`, `model`, `token_type` | Input/output tokens per agent |
| `nba_action_recommended_total` | Counter | `action`, `trigger_context` | NBA action distribution |
| `dispute_hold_triggered_total` | Counter | — | How often disputes block collection |
| `arrears_trajectory_distribution` | Counter | `trajectory` | Distribution of predicted trajectories |
| `db_query_duration_seconds` | Histogram | `query_name` | SQLite query performance |

### 3.2 Instrumentation (Python)

```python
# src/collection_assistant/observability/metrics.py
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

meter = metrics.get_meter("collection_assistant")

workflow_counter = meter.create_counter(
    "collection_workflow_total",
    description="Total collection workflow runs",
)
workflow_duration = meter.create_histogram(
    "collection_workflow_duration_seconds",
    description="End-to-end pipeline duration in seconds",
    unit="s",
)
agent_duration = meter.create_histogram(
    "agent_execution_duration_seconds",
    description="Per-agent execution duration",
    unit="s",
)
token_counter = meter.create_counter(
    "llm_tokens_used_total",
    description="LLM tokens used per agent call",
)
nba_counter = meter.create_counter(
    "nba_action_recommended_total",
    description="NBA actions recommended",
)
```

**Usage in agent code:**
```python
import time
with agent_duration.record_duration({"agent_name": "customer_profile", "stage": "1"}):
    result = await run_customer_profile_agent(state)
```

### 3.3 Grafana Dashboard — Pipeline Overview

**Dashboard: `FDE Collection Assistant — Pipeline`**

| Panel | Visualisation | Query |
|---|---|---|
| Total runs (24h) | Stat | `sum(increase(collection_workflow_total[24h]))` |
| Success rate | Gauge | `sum(rate(collection_workflow_total{status="completed"}[1h])) / sum(rate(collection_workflow_total[1h]))` |
| p50 / p95 / p99 pipeline latency | Stat row | `histogram_quantile(0.95, collection_workflow_duration_seconds_bucket)` |
| Agent latency heatmap | Heatmap | `agent_execution_duration_seconds_bucket` by `agent_name` |
| Token usage by agent | Bar chart | `sum by (agent_name) (increase(llm_tokens_used_total[1h]))` |
| NBA action distribution | Pie chart | `sum by (action) (increase(nba_action_recommended_total[24h]))` |
| Arrears trajectory distribution | Bar chart | `sum by (trajectory) (increase(arrears_trajectory_distribution[24h]))` |
| Dispute hold rate | Stat | `sum(increase(dispute_hold_triggered_total[24h]))` |

---

## 4. Pillar 2 — Logs (Loki via Grafana Cloud)

### 4.1 Log Schema

Every log line is structured JSON emitted via `structlog`. All logs include a correlation `workflow_id` so a complete run can be retrieved with a single Loki query.

```json
{
  "timestamp": "2026-06-03T09:15:30.412Z",
  "level": "info",
  "service": "collection-assistant-api",
  "workflow_id": "wf-abc12345",
  "customer_id": "CUST-001",
  "account_id": "ACC-001",
  "agent_name": "customer_profile",
  "stage": 1,
  "event": "agent_complete",
  "elapsed_ms": 1180,
  "input_tokens": 312,
  "output_tokens": 189,
  "risk_segment": "high"
}
```

### 4.2 Log Levels

| Level | When to Use |
|---|---|
| `DEBUG` | Tool call inputs/outputs, raw LLM messages (disabled in prod) |
| `INFO` | Agent start, agent complete, workflow start, workflow complete |
| `WARNING` | Retry triggered, agent returned unexpected output shape |
| `ERROR` | Agent failure, DB error, LLM API error |
| `CRITICAL` | Pipeline completely failed, data corruption detected |

### 4.3 Structlog Configuration

```python
# src/collection_assistant/observability/logging.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()

# Bind workflow context at start of each run
structlog.contextvars.bind_contextvars(
    workflow_id=workflow_id,
    customer_id=customer_id,
    account_id=account_id,
)
```

### 4.4 Key Log Events

| Event | Level | Logged When |
|---|---|---|
| `workflow_started` | INFO | Orchestrator receives new request |
| `agent_started` | INFO | Before each agent LLM call |
| `agent_complete` | INFO | After agent returns, includes elapsed_ms and token counts |
| `agent_retry` | WARNING | LLM call failed, retrying (includes attempt number) |
| `agent_failed` | ERROR | Agent exhausted retries or raised unhandled exception |
| `dispute_hold_triggered` | WARNING | Dispute agent returns `collection_hold=True` |
| `nba_recommended` | INFO | NBA agent produces final recommendation |
| `workflow_complete` | INFO | Full pipeline finished, includes total_ms |
| `workflow_failed` | ERROR | Pipeline could not complete |

### 4.5 Loki Queries (Grafana Explore)

```logql
# All events for a specific workflow run
{service="collection-assistant-api"} | json | workflow_id="wf-abc12345"

# All agent failures in the last hour
{service="collection-assistant-api"} | json | level="error" | event="agent_failed"

# All dispute holds triggered today
{service="collection-assistant-api"} | json | event="dispute_hold_triggered"

# Slow NBA agent calls (> 5s)
{service="collection-assistant-api"} | json | agent_name="nba" | elapsed_ms > 5000
```

---

## 5. Pillar 3 — Traces (Tempo via Grafana Cloud)

### 5.1 Trace Structure

Each workflow run is one **trace**. Each agent call is a **span**. Parallel agents produce sibling spans with overlapping timestamps — this makes the parallel execution visually clear in Tempo.

```
Trace: wf-abc12345  (7.8s total)
│
├── Span: orchestrator.run                    0ms → 7800ms
│     │
│     ├── Span: stage1.customer_profile       10ms → 1190ms   ← parallel
│     ├── Span: stage1.account_profile        10ms → 920ms    ← parallel
│     │
│     ├── Span: stage2.arrears_prediction     1200ms → 3300ms ← parallel
│     ├── Span: stage2.dispute                1200ms → 1900ms ← parallel
│     │
│     ├── Span: stage3.nba                    3300ms → 5700ms
│     └── Span: stage3.audit                  5700ms → 6200ms
```

### 5.2 Span Attributes

Every span carries these attributes for filtering in Tempo / Grafana:

```python
span.set_attributes({
    "workflow.id":          workflow_id,
    "workflow.trigger":     trigger_context,
    "customer.id":          customer_id,
    "account.id":           account_id,
    "agent.name":           agent_name,
    "agent.stage":          stage_number,
    "agent.model":          model_id,
    "llm.input_tokens":     input_tokens,
    "llm.output_tokens":    output_tokens,
    "nba.action":           nba_action,       # set on NBA span only
    "dispute.hold":         collection_hold,  # set on Dispute span only
    "arrears.trajectory":   trajectory,       # set on Arrears span only
})
```

### 5.3 OpenTelemetry Setup

```python
# src/collection_assistant/observability/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def configure_tracing(otlp_endpoint: str, otlp_token: str):
    exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        headers={"Authorization": f"Bearer {otlp_token}"},
    )
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

tracer = trace.get_tracer("collection_assistant")
```

**Usage in agents:**
```python
with tracer.start_as_current_span("agent.customer_profile") as span:
    span.set_attributes({"agent.name": "customer_profile", "agent.stage": 1})
    result = await run_agent(state)
    span.set_attribute("llm.output_tokens", result.usage.output_tokens)
```

### 5.4 Grafana Cloud OTel Exporter Config

```python
# src/collection_assistant/config.py
class Settings(BaseSettings):
    # Grafana Cloud OTel (free tier)
    grafana_otlp_endpoint: str = "https://otlp-gateway-prod-eu-west-0.grafana.net/otlp"
    grafana_otlp_token: str     # Instance ID:API key, base64 encoded
    otel_service_name: str = "collection-assistant-api"
```

---

## 6. Grafana Dashboards

### Dashboard 1: Pipeline Overview
- Total runs, success rate, error rate
- p50/p95/p99 end-to-end latency
- NBA action distribution (pie chart)
- Arrears trajectory distribution (bar)

### Dashboard 2: Agent Deep-Dive
- Per-agent latency over time (line chart)
- Agent error rate by agent name
- Token usage by agent and model (stacked bar)
- Stage 2 parallel efficiency (time saved vs sequential)

### Dashboard 3: Business Metrics
- NBA actions recommended per day (stacked bar by action type)
- Dispute hold rate trend (line chart)
- Risk segment distribution of processed customers (pie chart)
- Default probability distribution (histogram — shows spread across all runs)
- Arrears trajectory distribution (bar: improving / stable / deteriorating / critical)
- Average predicted DPD at +30d / +60d / +90d across all runs (grouped bar)

### Dashboard 4: Infrastructure
- Render.com API response time (via UptimeRobot webhook or synthetic probe)
- Database query latency
- Active workflow runs in-flight

---

## 7. Alerting Rules

All alerts configured in Grafana Cloud Alerting, notifications via free email.

| Alert | Condition | Severity | Action |
|---|---|---|---|
| High error rate | Agent error rate > 5% over 5 min | Critical | Email + check logs |
| Slow pipeline | p95 latency > 20s over 10 min | Warning | Check OTel traces for slow agent |
| Token spike | `llm_tokens_used_total` rate doubles in 15 min | Warning | Check for runaway retries |
| Dispute hold surge | Dispute holds > 20% of runs in 1h | Info | May indicate data issue |
| API down | `/health` returns non-200 for 2 consecutive checks | Critical | Render cold start or crash |

---

## 8. UI Chart Implementation (Streamlit + Plotly)

The arrears prediction card in the Streamlit UI uses **three distinct chart types** chosen for what each communicates best. Implemented with `plotly` (already a project dependency).

### Chart 1 — Semicircle Gauge: Default Probability

**Why:** A single scalar probability (0–100%) is best communicated as a dial. Instantly shows risk level without needing to read a number.

```python
# ui/components/arrears_card.py
import plotly.graph_objects as go

def render_default_probability_gauge(probability: float) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=probability * 100,
        number={"suffix": "%", "font": {"size": 28, "color": "#DC2626"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": "#DC2626"},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 33],  "color": "#DCFCE7"},   # green zone
                {"range": [33, 66], "color": "#FEF3C7"},   # amber zone
                {"range": [66, 100],"color": "#FEE2E2"},   # red zone
            ],
            "threshold": {
                "line": {"color": "#A100FF", "width": 3},
                "thickness": 0.85,
                "value": probability * 100,
            },
        },
        title={"text": "Default Probability", "font": {"size": 12}},
    ))
    fig.update_layout(height=180, margin=dict(l=10, r=10, t=30, b=10))
    return fig
```

### Chart 2 — Area Line Chart: DPD Trajectory

**Why:** Time-series trend (Now → +30d → +60d → +90d) is clearest as a line. The filled area below emphasises the growing debt burden. Slope of the line immediately communicates trajectory direction.

```python
def render_dpd_trajectory(current: int, d30: int, d60: int, d90: int) -> go.Figure:
    x = ["Now", "+30 days", "+60 days", "+90 days"]
    y = [current, d30, d60, d90]

    color = "#DC2626" if d90 > current else "#16A34A"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y,
        mode="lines+markers+text",
        line=dict(color=color, width=3),
        marker=dict(size=8, color=color),
        fill="tozeroy",
        fillcolor=f"rgba(220,38,38,0.1)",
        text=[str(v) for v in y],
        textposition="top center",
        textfont=dict(size=11, color=color, family="Inter"),
    ))
    fig.update_layout(
        height=160,
        margin=dict(l=10, r=10, t=10, b=30),
        yaxis=dict(title="Days Past Due", showgrid=True),
        xaxis=dict(showgrid=False),
        plot_bgcolor="#FAFAFA",
        paper_bgcolor="white",
    )
    return fig
```

### Chart 3 — Horizontal Bar Chart: Contributing Factors

**Why:** Ranked factors need comparison. Horizontal bars make the relative weight of each factor immediately readable. More legible than chips/tags which convey no quantitative weight.

```python
def render_risk_factors(factors: list[dict]) -> go.Figure:
    # factors: [{"name": "missed_3_consecutive", "weight": 0.45}, ...]
    factors_sorted = sorted(factors, key=lambda x: x["weight"])

    colors = ["#A100FF", "#D97706", "#DC2626"]   # low → high weight

    fig = go.Figure(go.Bar(
        x=[f["weight"] * 100 for f in factors_sorted],
        y=[f["name"] for f in factors_sorted],
        orientation="h",
        marker_color=colors[:len(factors_sorted)],
        text=[f"{f['weight']*100:.0f}%" for f in factors_sorted],
        textposition="outside",
    ))
    fig.update_layout(
        height=140,
        margin=dict(l=10, r=40, t=10, b=10),
        xaxis=dict(range=[0, 70], showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig
```

### Streamlit Layout in Arrears Card

```python
# ui/components/arrears_card.py
import streamlit as st
from collection_assistant.models.arrears import ArrearsPrediction

def render_arrears_card(pred: ArrearsPrediction):
    st.markdown("**Arrears Prediction** &nbsp; ✓ Agent 3", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.plotly_chart(
            render_default_probability_gauge(pred.default_probability),
            use_container_width=True, config={"displayModeBar": False}
        )
    with col2:
        st.plotly_chart(
            render_dpd_trajectory(
                pred.predicted_dpd_now,
                pred.predicted_dpd_30d,
                pred.predicted_dpd_60d,
                pred.predicted_dpd_90d,
            ),
            use_container_width=True, config={"displayModeBar": False}
        )

    st.markdown("**Contributing Risk Factors**")
    st.plotly_chart(
        render_risk_factors(pred.contributing_factors),
        use_container_width=True, config={"displayModeBar": False}
    )
```

---

## 9. Observability Checklist (Pre-Demo)

- [ ] Grafana Cloud account created, OTLP endpoint + token saved to GitHub Secrets
- [ ] OTel exporter configured and pointing to Grafana Cloud
- [ ] Run one full pipeline — verify trace appears in Tempo
- [ ] Verify structured logs appear in Loki with correct `workflow_id`
- [ ] Verify metrics appear in Prometheus (check `collection_workflow_total`)
- [ ] Import Pipeline Overview dashboard from `docs/grafana-dashboards/pipeline.json`
- [ ] Set up at least one alert rule (error rate > 5%)
- [ ] Confirm alert email received after triggering a test error
