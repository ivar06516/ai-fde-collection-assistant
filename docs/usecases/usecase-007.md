# UC-007: Review Audit Trail and Decision Lineage

## Overview

| Field | Value |
|---|---|
| **ID** | UC-007 |
| **Actor** | Compliance Officer, Collection Agent |
| **Goal** | Retrieve and review the complete per-agent decision trail for a completed workflow to understand why the NBA recommendation was produced and satisfy audit requirements |
| **Priority** | P0 — transparency is a stated PoC goal |
| **Delivery Phase** | Phase 7 (Audit Agent), Phase 8 (API endpoint), Phase 9 (UI expander) |
| **Pipeline Stage** | Stage 3 — Audit Agent runs after NBA Agent |
| **Model** | `llama-3.1-8b-instant` (lightweight logging agent) |

---

## Preconditions

- A workflow has been completed (`workflow_status = "completed"`)
- `workflow_id` is known (returned by UC-001 step 3)
- `workflow_audit` table has been written by the Audit Agent

---

## Main Flow

| Step | Actor | Action | System Response |
|---|---|---|---|
| 1 | Collection Agent | Scrolls to bottom of Screen 3 Results Dashboard | "▾ Full Audit Trail" expandable section visible |
| 2 | Agent | Clicks to expand the audit section | UI calls `GET /collections/{workflow_id}/audit` |
| 3 | System | FastAPI queries `workflow_audit` table for `workflow_id` | Returns structured JSON with per-agent steps |
| 4 | System | UI renders Screen 4 (Audit Trail) | 6 agent rows: icon, name, elapsed time, input summary, output summary |
| 5 | Compliance Officer | Reviews each agent's input and output | Verifies: correct data used, dispute hold checked, arrears risk considered before NBA |
| 6 | Compliance Officer | Inspects NBA rationale text | Confirms recommendation is consistent with decision inputs |

---

## Audit Agent Sub-Flow (Runs After NBA Agent)

| Step | Tool Called | Input | Output |
|---|---|---|---|
| 1 | `log_agent_step` × 6 | Per-agent summary from `CollectionWorkflowState` | Structured step records: name, stage, elapsed_ms, tokens, input/output summary |
| 2 | `build_decision_lineage` | All 6 step records | Ordered decision chain with NBA rationale at the end |
| 3 | `generate_audit_report` | Decision lineage | Writes full record to `workflow_audit` table |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | Workflow failed before NBA | Audit trail shows steps up to the failing agent; subsequent agents marked "not reached" |
| AF-02 | Dispute hold was active | Audit trail explicitly shows `collection_hold = True` in Dispute Agent output row |
| AF-03 | `workflow_id` not found in DB | `GET /audit` returns 404; UI shows "Audit record not found" |

---

## Postconditions

- Compliance officer has complete, immutable decision record
- `workflow_audit` record persists in SQLite (append-only by design)
- Full JSON state available for programmatic analysis

---

## Acceptance Criteria

### AC-007-01: All Six Agents Appear in Audit Trail
- **Given** a completed pipeline run with `workflow_status = "completed"`
- **When** the Audit Agent runs and `GET /audit` is called
- **Then** the `agents` array in the response contains exactly 6 entries in order: `customer_profile`, `account_profile`, `arrears_prediction`, `dispute`, `nba`, `audit`
- **Verified by** Phase 7 unit test asserting audit response structure

### AC-007-02: Input and Output Summaries Match State
- **Given** John Smith (`CUST-001`) with `days_past_due = 45`
- **When** the Audit Trail is rendered
- **Then** the `account_profile` agent row shows `output_summary.days_past_due = 45`; the `nba` agent row shows `output_summary.action` matching `state.nba_recommendation.action`
- **Verified by** Phase 7 unit test cross-referencing audit output against state

### AC-007-03: Elapsed Times Recorded for Every Agent
- **Given** a completed pipeline run
- **When** `GET /audit` returns
- **Then** every agent entry has `elapsed_ms > 0` and the sum of all `elapsed_ms` values is ≤ `total_execution_ms` (parallel execution means sum > total is possible; sum ≤ total * 2 is a reasonable bound)
- **Verified by** Phase 7 unit test asserting elapsed_ms presence and bounds

### AC-007-04: Audit Record Persists in DB
- **Given** a completed workflow run
- **When** the Audit Agent writes its report
- **Then** a row exists in `workflow_audit` with the matching `workflow_id`; `nba_action` is non-null; `full_state_json` is non-null and parseable as valid JSON; `status = "completed"`
- **Verified by** Phase 11 integration test querying `workflow_audit` directly after run

### AC-007-05: Dispute Hold Visible in Audit Trail
- **Given** Sarah Jones (`CUST-002`) whose dispute triggered `collection_hold = True`
- **When** the Audit Trail is rendered
- **Then** the `dispute` agent row shows `output_summary.collection_hold = true`; the `nba` agent row shows `output_summary.action = "place_on_hold"` and `output_summary.blocked_by_dispute = true`
- **Verified by** Phase 11 named-scenario integration test for Sarah Jones

### AC-007-06: Audit Trail Accessible via API Independently of UI
- **Given** a completed `workflow_id`
- **When** `GET /collections/{workflow_id}/audit` is called directly
- **Then** response is HTTP 200 with valid JSON matching the full audit schema; no authentication required (PoC scope)
- **Verified by** Phase 8 API integration test

### AC-007-07: Audit Agent Uses Haiku Model (Cost Control)
- **Given** any completed pipeline run
- **When** token usage metrics are checked
- **Then** `llm_tokens_used_total{agent="audit",model="llama-3.1-8b-instant"}` counter is incremented; Haiku is not used for any other agent
- **Verified by** Grafana `llm_tokens_used_total` metric filtered by model

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §2.2.7 Audit Agent, §5.2 `workflow_audit` table schema, §10.2 Screen 4, §11 `GET /collections/{id}/audit` |
| **Deployment** | Render.com FastAPI reads `workflow_audit` SQLite; no LLM call for `GET /audit` endpoint — pure DB read; `st.expander()` in Streamlit |
| **Observability** | The audit trail IS an observability artefact — `full_state_json` in `workflow_audit` is queryable; Loki query `workflow_id="wf-abc123"` returns all 6 agent log events in sequence |
| **SRE** | Every completed workflow MUST have a `workflow_audit` record — missing record = P2 incident (data integrity); `workflow_audit` uses append-only insert (no UPDATE on existing records); `workflow_id` primary key prevents duplicates |
