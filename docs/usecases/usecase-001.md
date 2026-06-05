# UC-001: Run Full Collection Analysis

## Overview

| Field | Value |
|---|---|
| **ID** | UC-001 |
| **Actor** | Collection Agent |
| **Goal** | Trigger the full multi-agent pipeline from the UI and receive a complete NBA recommendation with all four agent outputs visible |
| **Priority** | P0 |
| **Delivery Phase** | Phase 7 (Orchestrator + LangGraph), Phase 8 (FastAPI), Phase 9 (Streamlit UI) |
| **Related Agents** | All 7 (Orchestrator, Customer Profile, Account Profile, Arrears Prediction, Dispute, NBA, Audit) |

---

## Preconditions

- SQLite DB is seeded (UC-008 completed)
- `GROQ_API_KEY` is set in the deployment environment (free — console.groq.com)
- FastAPI backend is running — `GET /health` returns `{"status": "healthy"}`
- Streamlit UI is accessible at `http://localhost:8501` (local) or Streamlit Community Cloud (deployed)

---

## Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | Collection Agent | Opens Streamlit UI — Input Panel (Screen 1) | Customer ID / Account ID dropdowns populated from SQLite `customers` and `accounts` tables |
| 2 | Collection Agent | Selects Customer ID, Account ID, Trigger context; clicks **Run Analysis** | UI calls `POST /collections/recommend` |
| 3 | System | FastAPI creates `workflow_id`, starts LangGraph pipeline | Returns `202 Accepted` with `{"workflow_id": "wf-...", "status": "in_progress"}` |
| 4 | System | UI opens `GET /collections/{workflow_id}/stream` (SSE) | Execution Panel (Screen 2) appears; all agent rows in waiting state |
| 5 | System | Orchestrator launches Stage 1 agents in parallel | SSE events: `customer_profile → running`, `account_profile → running` |
| 6 | System | Stage 1 agents complete | SSE events: both rows update to ✅ Complete with elapsed times |
| 7 | System | Orchestrator launches Stage 2 agents in parallel | SSE events: `arrears_prediction → running`, `dispute → running` |
| 8 | System | Stage 2 agents complete | SSE events: both rows update to ✅ Complete |
| 9 | System | Orchestrator launches NBA Agent (Stage 3) | SSE: `nba → running` |
| 10 | System | NBA + Audit agents complete | SSE: `workflow_complete` event fired |
| 11 | System | UI transitions to Results Dashboard (Screen 3) | Four agent output cards + NBA recommendation card rendered |

---

## Alternative Flows

| ID | Condition | System Behaviour |
|---|---|---|
| AF-01 | `collection_hold = true` (dispute active) | NBA card shows `place_on_hold`; hold reason displayed |
| AF-02 | `arrears_trajectory = critical` | NBA card shows `escalate_to_legal` or `offer_settlement` |
| AF-03 | Agent fails and exhausts 3 retries | Agent row shows ❌; `workflow_status = "error"`; error_log populated; graceful degradation |
| AF-04 | Customer ID not found in DB | FastAPI 404; UI shows "Customer not found — re-seed database" |
| AF-05 | Groq API timeout | Exponential backoff × 3; if all fail, `workflow_status = "error"` |

---

## Postconditions

- `workflow_audit` record written with full `CollectionWorkflowState` JSON
- NBA recommendation surfaced in Screen 3
- Full audit trail accessible via `GET /collections/{workflow_id}/audit`
- `collection_workflow_total` Prometheus counter incremented

---

## Acceptance Criteria

### AC-001-01: Pipeline Completes Within SLO
- **Given** a seeded DB with a valid `customer_id` and `account_id`
- **When** the Collection Agent clicks Run Analysis
- **Then** the full pipeline completes and `workflow_status = "completed"` is returned within **30 seconds** (p95 — Groq free tier)
- **Verified by** Phase 11 integration test + Grafana `collection_workflow_duration_seconds` p95 ≤ 30s

### AC-001-02: All Five Agent Outputs Populated
- **Given** a successful pipeline run
- **When** the Results Dashboard (Screen 3) renders
- **Then** all four agent output cards are visible: Customer Profile, Account Profile, Arrears Prediction, Dispute Summary — all containing non-empty data
- **Verified by** Phase 11 UI integration test asserting card presence and non-null fields

### AC-001-03: NBA Recommendation Card is Present and Complete
- **Given** a pipeline run with `workflow_status = "completed"`
- **When** Screen 3 renders
- **Then** the NBA Recommendation card displays: a valid action from the 9-action catalogue, a channel, a rationale text of ≥ 50 characters, a confidence score between 0.0 and 1.0, and at least 2 alternative actions
- **Verified by** Phase 11 integration test asserting NBA card fields

### AC-001-04: SSE Events Arrive in Stage Order
- **Given** a running pipeline
- **When** the UI listens on `GET /collections/{workflow_id}/stream`
- **Then** `agent_update` events arrive with stage numbers in ascending order: Stage 1 events before Stage 2, Stage 2 before Stage 3; `workflow_complete` event fires last
- **Verified by** Phase 8 FastAPI unit test on SSE event ordering

### AC-001-05: Audit Record Written to DB
- **Given** a pipeline run that reaches `workflow_status = "completed"`
- **When** the Audit Agent completes
- **Then** a record exists in `workflow_audit` table with the matching `workflow_id`, a non-null `nba_action`, and a non-null `full_state_json`
- **Verified by** Phase 11 integration test querying `workflow_audit` after run

### AC-001-06: Error State Shown on Agent Failure
- **Given** the Groq API returns errors for all 3 retries on a specific agent
- **When** the pipeline runs
- **Then** the failed agent row in the Execution Panel shows ❌ Error; `workflow_status = "error"`; remaining agents do not execute; UI does not crash
- **Verified by** Phase 11 integration test with mocked LLM failure

### AC-001-07: Workflow Re-run is Idempotent
- **Given** a `workflow_id` for a completed run
- **When** the same `customer_id` + `account_id` are submitted again
- **Then** a new `workflow_id` is issued; new `workflow_audit` record is created; prior record is unchanged
- **Verified by** Phase 11 integration test running the same input twice

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §1.2 Goals, §2.1 Architecture, §2.2.1–2.2.7 All Agents, §10.2 Screens 1–3, §11 API Contract |
| **Deployment** | Render.com (FastAPI + SQLite), Streamlit Community Cloud (UI), Groq free tier LLM |
| **Observability** | `collection_workflow_total` counter, `collection_workflow_duration_seconds` histogram, root Tempo trace span per workflow, `workflow_started` + `workflow_complete` Loki log events |
| **SRE** | SLO: p95 latency ≤ 15s; SLO: pipeline success rate ≥ 95%; Alert: error rate > 10% over 5 min; `sre_strategy.md §8` Incident Runbook |
