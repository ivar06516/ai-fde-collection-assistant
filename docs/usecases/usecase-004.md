# UC-004: Predict Arrears Trajectory

## Overview

| Field | Value |
|---|---|
| **ID** | UC-004 |
| **Actor** | System (Arrears Prediction Agent triggered by Orchestrator) |
| **Goal** | Analyse payment history and behavioural signals from Stage 1 state to forecast arrears trajectory, default probability, and DPD at +30/+60/+90 days |
| **Priority** | P0 |
| **Delivery Phase** | Phase 4 |
| **Pipeline Stage** | Stage 2 — parallel with UC-005 |
| **Model** | `llama-3.3-70b-versatile` |

---

## Preconditions

- `state.customer_profile` and `state.account_profile` are populated (Stage 1 complete)
- `account_profile.payment_history` contains ≥ 3 months of data
- Stage 2 parallel execution started alongside UC-005

---

## Main Flow

| Step | Tool Called | Input | Output |
|---|---|---|---|
| 1 | `analyse_payment_pattern` | `payment_history_12m` | Consecutive missed payments count, avg payment %, payment trend direction |
| 2 | `calculate_arrears_trajectory` | Pattern + DPD history | `improving / stable / deteriorating / critical` |
| 3 | `predict_default_probability` | Pattern + `risk_segment` + DPD | Float 0.0–1.0 |
| 4 | `estimate_future_arrears` | Trend rate + current balance | Predicted DPD at +30d, +60d, +90d; projected balance at +30d |
| 5 | `identify_risk_factors` | Full payment pattern | Ranked list: `[{"name": str, "weight": float}]` sorted by weight descending |
| 6 | Returns `ArrearsPrediction` TypedDict | — | Written to `state.arrears_prediction` |
| 7 | SSE event emitted | — | `{"agent":"arrears_prediction","stage":2,"status":"complete"}` |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | Payment history < 3 months | `confidence < 0.5` returned; NBA Agent includes low-confidence caveat in rationale |
| AF-02 | All recent payments on time, DPD trending down | `arrears_trajectory = "improving"`; `default_probability < 0.3` |
| AF-03 | DPD already > 90 | `arrears_trajectory = "critical"`; `default_probability > 0.85`; NBA routes to `escalate_to_legal` |
| AF-04 | `account_status = "written_off"` | Prediction still runs; `arrears_trajectory = "critical"` |

---

## Postconditions

- `state.arrears_prediction` populated with trajectory, probability, DPD forecasts, and ranked factors
- Three charts rendered on Screen 3: gauge dial, area line chart, horizontal bar chart

---

## Acceptance Criteria

### AC-004-01: Trajectory is One of Four Valid Values
- **Given** any account with payment history
- **When** the Arrears Prediction Agent runs
- **Then** `arrears_prediction.arrears_trajectory` is one of: `"improving"`, `"stable"`, `"deteriorating"`, `"critical"`
- **Verified by** Phase 4 unit test checking enum constraint

### AC-004-02: Default Probability is Within Valid Range
- **Given** any account
- **When** `predict_default_probability` tool returns
- **Then** `0.0 ≤ arrears_prediction.default_probability ≤ 1.0`
- **Verified by** Phase 4 unit test with assertion on float bounds

### AC-004-03: Deteriorating Account Shows Increasing DPD Forecast
- **Given** a payment pattern with 3 consecutive missed payments and DPD > 0
- **When** `estimate_future_arrears` and `calculate_arrears_trajectory` tools run
- **Then** `predicted_dpd_30 > current_dpd`, `predicted_dpd_60 > predicted_dpd_30`, `predicted_dpd_90 > predicted_dpd_60`
- **Verified by** unit test `test_arrears_prediction_agent.py::test_deteriorating_dpd_forecast_increases`

### AC-004-04: Improving Account Shows Decreasing or Stable DPD Forecast
- **Given** Emma Patel (`CUST-004`, overdraft, DPD 35, hardship) with recent on-time payments
- **When** `calculate_arrears_trajectory` tool runs with `trend="improving"`
- **Then** `arrears_trajectory = "improving"` and `predicted_dpd_30 ≤ current_dpd`
- **Verified by** unit test `test_arrears_prediction_agent.py::test_improving_dpd_forecast_stable_or_decreasing`

### AC-004-05: Critical Trajectory for 90+ DPD Account
- **Given** Michael Okonkwo (`CUST-003`, personal_loan, DPD 92, high risk)
- **When** `calculate_arrears_trajectory` and `predict_default_probability` tools run
- **Then** `arrears_trajectory = "critical"` and `default_probability > 0.85`
- **Verified by** unit test `test_arrears_prediction_agent.py::test_critical_trajectory_high_dpd`

### AC-004-06: Contributing Factors Returned as Ranked List
- **Given** any account with identifiable risk patterns
- **When** `identify_risk_factors` returns
- **Then** `contributing_risk_factors` is a non-empty list of `{"name": str, "weight": float}` dicts; sorted by `weight` descending; each weight is in range 0.0–1.0
- **Verified by** unit test `test_arrears_prediction_agent.py::test_risk_factors_ranked_list_structure`

### AC-004-07: Low History Confidence Flagged
- **Given** an account with only 2 months of payment history
- **When** `estimate_future_arrears` runs with `months_available < 3`
- **Then** returned `confidence_score < 0.5`; the agent includes a low-confidence caveat
- **Verified by** unit test `test_arrears_prediction_agent.py::test_low_history_reduces_confidence`

### AC-004-08: Three Charts Rendered in UI
- **Given** a completed pipeline run
- **When** Screen 3 Results Dashboard renders
- **Then** the Arrears Prediction card contains: (1) a gauge dial showing `default_probability` as a percentage, (2) an area line chart with 4 DPD data points (Now, +30d, +60d, +90d), (3) a horizontal bar chart with ≥ 2 ranked factors
- **Verified by** Phase 9 Streamlit UI test; HTML preview: `ui/previews/preview_03_results.html`

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §2.2.4 Arrears Prediction Agent, §6.1 Stage 2, §10.2 Screen 3 Arrears Card, §Q8 (resolved — 3 chart types) |
| **Deployment** | Render.com FastAPI; Groq API (free, `llama-3.3-70b-versatile`); no additional DB query (uses Stage 1 state) |
| **Observability** | `arrears_trajectory_distribution{trajectory}` counter (key portfolio-health business metric); `agent_execution_duration_seconds{agent="arrears_prediction"}` histogram; `stage2.arrears_prediction` Tempo span with `arrears.trajectory` + `arrears.default_probability` attributes; Grafana Dashboard 3 Business Metrics |
| **SRE** | Agent error rate SLO ≤ 2%; p95 target < 3s for this agent; NBA recommendation quality degrades if this agent fails — treated as P2 impact even in partial failure |
