# UC-006: Generate Next Best Action Recommendation

## Overview

| Field | Value |
|---|---|
| **ID** | UC-006 |
| **Actor** | System (NBA Agent triggered by Orchestrator after Stage 2 completes) |
| **Goal** | Synthesise all four upstream agent outputs into a single prioritised action with channel, rationale, confidence score, and ranked alternatives |
| **Priority** | P0 — the primary deliverable of the entire system |
| **Delivery Phase** | Phase 6 |
| **Pipeline Stage** | Stage 3 — sequential, requires all Stage 1 and Stage 2 outputs |
| **Model** | `claude-opus-4-8` (highest reasoning model) |

---

## Preconditions

- All four state fields populated: `customer_profile`, `account_profile`, `arrears_prediction`, `dispute_summary`
- Stage 2 fully complete (both Arrears Prediction and Dispute agents finished)

---

## NBA Action Catalogue

| Action | Trigger Condition |
|---|---|
| `initiate_call` | DPD 30–90, no hold, reachable by mobile/phone |
| `send_sms` | Low-medium DPD, improving/stable trajectory, mobile preferred |
| `send_email` | Low-medium DPD, email preferred channel |
| `offer_payment_plan` | Medium DPD, willing customer segment, capacity to pay |
| `offer_settlement` | High DPD, high balance, deteriorating trajectory |
| `place_on_hold` | `collection_hold = True` (dispute active) |
| `escalate_to_legal` | DPD > 90, critical trajectory, high default probability |
| `flag_for_writeoff` | `account_status = "written_off"` or DPD > 150 |
| `no_action_required` | Improving trajectory, recent payment, DPD < 15 |

---

## Main Flow

| Step | Tool Called | Input | Output |
|---|---|---|---|
| 1 | `evaluate_action_eligibility` | `dispute_summary.collection_hold`, `account_profile.account_status` | Filtered list of eligible actions (hard constraints applied) |
| 2 | Arrears signal routing | `arrears_trajectory`, `default_probability` | Boosted weights for urgency-matched actions |
| 3 | `score_action_options` | Full state + eligible actions | Each action scored 0.0–1.0 by Claude Opus 4.8 |
| 4 | `generate_recommendation_rationale` | Top-scored action + full state | 2–4 sentence human-readable rationale |
| 5 | `validate_against_policy` | Final recommendation | Confirms action is in approved catalogue |
| 6 | Returns `NBARecommendation` TypedDict | — | Written to `state.nba_recommendation` |
| 7 | SSE event emitted | — | `{"agent":"nba","stage":3,"status":"complete","output":{"action":"...","confidence_score":...}}` |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | `collection_hold = True` | Action forced to `place_on_hold` or `no_action_required`; `blocked_by_dispute = True`; rationale cites dispute reference |
| AF-02 | `default_probability > 0.85` + `trajectory = critical` | Action = `escalate_to_legal` or `offer_settlement`; no lighter-touch alternatives in top 3 |
| AF-03 | `account_status = "written_off"` | Action = `flag_for_writeoff`; rationale explains status |
| AF-04 | `trajectory = improving` + `DPD < 15` | Action = `no_action_required` or `send_sms`; rationale notes positive payment trend |
| AF-05 | `arrears_prediction.confidence < 0.5` | Rationale includes "based on limited payment history — recommend manual review" |

---

## Postconditions

- `state.nba_recommendation` populated: action, channel, rationale, confidence, alternatives
- NBA card rendered in Screen 3 with Accenture purple border
- `nba_action_recommended_total` Prometheus counter incremented

---

## Acceptance Criteria

### AC-006-01: Action is Always From the Approved Catalogue
- **Given** any valid input state
- **When** the NBA Agent returns
- **Then** `nba_recommendation.action` is one of the 9 approved actions: `initiate_call`, `send_sms`, `send_email`, `offer_payment_plan`, `offer_settlement`, `place_on_hold`, `escalate_to_legal`, `flag_for_writeoff`, `no_action_required`
- **Verified by** Phase 6 unit test asserting action against the approved enum

### AC-006-02: Dispute Hold Enforces Hard Constraint
- **Given** `dispute_summary.collection_hold = True`
- **When** the NBA Agent runs
- **Then** `nba_recommendation.action` is either `"place_on_hold"` or `"no_action_required"`; `blocked_by_dispute = True`; no outbound contact action (`initiate_call`, `send_sms`, `send_email`) appears in the recommendation or alternatives
- **Verified by** Phase 11 integration test for Sarah Jones (Dispute Hold scenario)

### AC-006-03: Critical Trajectory Routes to Urgent Actions
- **Given** `arrears_trajectory = "critical"` and `default_probability > 0.85` and no dispute hold
- **When** the NBA Agent runs
- **Then** `nba_recommendation.action` is one of `"escalate_to_legal"` or `"offer_settlement"`
- **Verified by** Phase 11 named-scenario integration test for Michael Tan (Critical Arrears)

### AC-006-04: Improving Trajectory Routes to Light-Touch Actions
- **Given** `arrears_trajectory = "improving"` and `days_past_due < 15` and no dispute hold
- **When** the NBA Agent runs
- **Then** `nba_recommendation.action` is one of `"no_action_required"` or `"send_sms"`
- **Verified by** Phase 11 named-scenario integration test for Emily Carter (Improving Customer)

### AC-006-05: Rationale References Specific State Values
- **Given** John Smith with `days_past_due = 45`, `preferred_channel = "mobile"`, `arrears_trajectory = "deteriorating"`
- **When** the NBA Agent generates a rationale
- **Then** the `rationale` string contains at least two of: the DPD value (`45`), the trajectory label (`deteriorating`), the channel (`mobile`), or the risk segment (`high`)
- **Verified by** Phase 6 unit test with substring assertions on rationale text

### AC-006-06: Confidence Score is Within Valid Range
- **Given** any input state
- **When** the NBA Agent returns
- **Then** `0.0 ≤ nba_recommendation.confidence_score ≤ 1.0`
- **Verified by** Phase 6 unit test asserting float bounds

### AC-006-07: At Least Two Alternative Actions Returned
- **Given** any input state with more than 2 eligible actions
- **When** the NBA Agent returns
- **Then** `len(nba_recommendation.alternative_actions) ≥ 2`; each alternative has an `action` and a `score`; all alternative actions are from the approved catalogue
- **Verified by** Phase 6 unit test asserting alternatives list length and structure

### AC-006-08: Written-Off Account Returns Correct Action
- **Given** Karen Wilson (`CUST-006`) with `account_status = "written_off"`
- **When** the NBA Agent runs
- **Then** `nba_recommendation.action = "flag_for_writeoff"`
- **Verified by** Phase 11 named-scenario integration test for Karen Wilson

### AC-006-09: NBA Completes Within Latency Budget
- **Given** a standard pipeline run
- **When** the NBA Agent (Stage 3, Claude Opus 4.8) runs
- **Then** NBA Agent completes in < 5 seconds (p95)
- **Verified by** Grafana `agent_execution_duration_seconds{agent="nba"}` p95

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §2.2.6 NBA Agent, §2.2.6 action catalogue (9 actions), §6.1 Stage 3, §6.2 Dispute Hold Path, §10.2 Screen 3 NBA Card |
| **Deployment** | Render.com FastAPI; Anthropic API (`claude-opus-4-8` — highest cost, justified by synthesis complexity); prompt caching on policy/constraint system prompt |
| **Observability** | `nba_action_recommended_total{action}` counter (key business metric, Grafana Dashboard 2 pie chart); `agent_execution_duration_seconds{agent="nba"}` histogram (Stage 3 bottleneck); `stage3.nba` Tempo span with `nba.action`, `nba.confidence`, `nba.blocked_by_dispute` attributes; `nba_recommended` INFO Loki event |
| **SRE** | NBA recommendation rate SLO ≥ 98% of completed workflows; p95 latency for NBA ≤ 5s; highest-cost agent — Opus 4.8 token spend tracked via `llm_tokens_used_total{agent="nba",model="claude-opus-4-8"}`; NBA failure = `human_review` pipeline status |
