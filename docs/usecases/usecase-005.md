# UC-005: Detect Disputes and Collection Hold

## Overview

| Field | Value |
|---|---|
| **ID** | UC-005 |
| **Actor** | System (Dispute Agent triggered by Orchestrator) |
| **Goal** | Query `disputes` table for active disputes, determine if a `collection_hold` flag blocks all outbound NBA actions |
| **Priority** | P0 — highest compliance criticality; a missed hold is a regulatory failure |
| **Delivery Phase** | Phase 5 |
| **Pipeline Stage** | Stage 2 — parallel with UC-004 |
| **Model** | `llama-3.3-70b-versatile` |

---

## Preconditions

- `state.account_profile` is populated (Stage 1 complete)
- `disputes` table seeded with relevant records
- Stage 2 parallel execution started alongside UC-004

---

## Main Flow

| Step | Tool Called | DB Table | Output |
|---|---|---|---|
| 1 | `get_active_disputes` | `disputes` (status IN `open`,`under_review`) | List of active dispute objects |
| 2 | `classify_dispute_type` | — (LLM classification) | `billing_error / fraud_claim / identity_theft / service_dispute / payment_dispute` |
| 3 | `check_collection_hold_flag` | `disputes.collection_hold` | `bool`; hold reason string if True |
| 4 | `get_dispute_history` | `disputes` (resolved) | Prior resolved disputes list |
| 5 | `get_resolution_timeline` | `disputes` | Days open, escalation status for each active dispute |
| 6 | Returns `DisputeSummary` TypedDict | — | Written to `state.dispute_summary` |
| 7 | SSE event emitted | — | `{"agent":"dispute","stage":2,"status":"complete","output":{"collection_hold":...}}` |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | Active dispute with `collection_hold = 1` | `dispute_summary.collection_hold = True`; NBA hard-constrained to `place_on_hold` or `no_action_required` only |
| AF-02 | Multiple active disputes | All listed in `active_disputes`; single `collection_hold = True` if any has `collection_hold = 1` |
| AF-03 | Dispute resolved < 7 days ago | In `resolution_history`; NBA rationale includes caution note even without active hold |
| AF-04 | No disputes found | `has_active_dispute = False`, `collection_hold = False`; NBA proceeds with full action catalogue |

---

## Postconditions

- `state.dispute_summary.collection_hold` set to `True` or `False`
- If `True`, NBA Agent will enforce hard constraint at Stage 3
- `dispute_hold_triggered_total` Prometheus counter incremented if hold = True

---

## Acceptance Criteria

### AC-005-01: Active Dispute Sets Collection Hold True
- **Given** Sarah Jones (`CUST-002` / `ACC-002`) has an active `identity_theft` dispute (`DISP-001`) with `collection_hold = 1` in DB
- **When** the Dispute Agent runs for `ACC-002`
- **Then** `dispute_summary.collection_hold = True` and `dispute_summary.hold_reason` is non-empty
- **Verified by** unit test `test_dispute_agent.py::test_active_dispute_sets_hold_true`

### AC-005-02: No Active Disputes Returns Hold False
- **Given** James Chen (`CUST-001` / `ACC-001`) has no active disputes (0 open rows for `ACC-001`)
- **When** `check_collection_hold` tool runs for `ACC-001`
- **Then** `collection_hold = False` and `hold_reason` is empty
- **Verified by** unit test `test_dispute_agent.py::test_no_disputes_returns_hold_false`

### AC-005-03: Multiple Active Disputes All Listed
- **Given** David Brown (`CUST-007` / `ACC-007`) has 2 active disputes in the DB (seeded)
- **When** the Dispute Agent runs for `ACC-007`
- **Then** `dispute_summary.active_disputes` list length is 2; both dispute IDs are present
- **Verified by** unit test `test_dispute_agent.py::test_multiple_disputes_all_listed`

### AC-005-04: Resolved Dispute Does Not Set Hold
- **Given** a dispute with `status = "resolved"` in the DB
- **When** the Dispute Agent runs
- **Then** the resolved dispute appears in `dispute_summary.resolution_history` but NOT in `active_disputes`; `collection_hold = False` (assuming no other open disputes)
- **Verified by** Phase 5 unit test with resolved dispute fixture

### AC-005-05: NBA is Blocked When Hold is Active
- **Given** `dispute_summary.collection_hold = True` (any active dispute with hold flag)
- **When** the NBA Agent runs in UC-006
- **Then** `nba_recommendation.action` is one of `["place_on_hold", "no_action_required"]`; `nba_recommendation.blocked_by_dispute = True`; no outbound contact action is returned regardless of arrears trajectory
- **Verified by** unit test `test_dispute_agent.py::test_nba_blocked_when_hold_active` + `test_nba_tools.py::test_collection_hold_restricts_actions`

### AC-005-06: Dispute Type Classification is Accurate
- **Given** a dispute with description containing "charge I did not authorise"
- **When** `classify_dispute_type` tool runs
- **Then** returned type is `"fraud_claim"` or `"billing_error"` (not `"identity_theft"` or `"service_dispute"`)
- **Verified by** unit test `test_dispute_agent.py::test_classify_dispute_type_fraud_or_billing`

### AC-005-07: Resolution Timeline Returns Days Open
- **Given** an active dispute opened N days ago
- **When** `get_resolution_timeline` tool runs
- **Then** returned dict has `days_open >= 0`; `escalated` boolean; `dispute_id` present
- **Verified by** unit test `test_dispute_agent.py::test_resolution_timeline_days_open`

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §2.2.5 Dispute Agent, §5.2 `disputes` table schema, §6.1 Stage 2, §6.2 Dispute Hold Path |
| **Deployment** | Render.com FastAPI + SQLite `disputes` table; Groq API (free, `llama-3.3-70b-versatile`) |
| **Observability** | `dispute_hold_triggered_total` counter (compliance business metric); `agent_execution_duration_seconds{agent="dispute"}` histogram; `dispute_hold_triggered` WARNING Loki event; `stage2.dispute` Tempo span with `dispute.hold` boolean attribute; Alert: hold rate > 30% of runs in 1h |
| **SRE** | **Zero tolerance for missed hold** — AC-005-05 must pass in every integration test run before any production deploy; Agent error rate SLO ≤ 2%; if Dispute Agent fails, NBA must not produce outbound contact recommendations (pipeline must error, not default to no-hold) |
