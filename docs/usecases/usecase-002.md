# UC-002: Build Customer Profile

## Overview

| Field | Value |
|---|---|
| **ID** | UC-002 |
| **Actor** | System (Customer Profile Agent triggered by Orchestrator) |
| **Goal** | Query `customers` and `interaction_history` tables to build a 360° customer profile and populate `state.customer_profile` |
| **Priority** | P0 |
| **Delivery Phase** | Phase 3 |
| **Pipeline Stage** | Stage 1 — parallel with UC-003 |
| **Model** | `llama-3.3-70b-versatile` (free_cloud/default) · `llama-3.3-70b-versatile` (premium) |

---

## Preconditions

- `customer_id` is present in workflow state
- SQLite DB is seeded; `customers` and `interaction_history` tables populated
- Stage 1 parallel execution started by Orchestrator

---

## Main Flow

| Step | Tool Called | DB Table | Output |
|---|---|---|---|
| 1 | `get_customer_demographics` | `customers` | name, DOB, employment, income, city, postcode |
| 2 | `get_contact_preferences` | `customers` | `preferred_channel`, `preferred_time` |
| 3 | `get_interaction_history` | `interaction_history` | last 12 interactions with outcomes |
| 4 | `classify_risk_segment` | — (computed) | `low / medium / high / hardship` |
| 5 | `detect_hardship_signals` | `customers` | hardship flag, reason (medical/unemployment/family/none) |
| 6 | Returns `CustomerProfile` TypedDict | — | Written to `state.customer_profile` |
| 7 | SSE event emitted | — | `{"agent":"customer_profile","stage":1,"status":"complete"}` |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | `customer_id` not found in `customers` table | `CustomerNotFoundError` raised; `workflow_status = "error"`; error_log entry created |
| AF-02 | Zero rows in `interaction_history` | `prior_collection_interactions = 0`; hardship inferred from demographics only |
| AF-03 | LLM classification call times out | Retry × 3; if all fail, agent marks status as failed |

---

## Postconditions

- `state.customer_profile` populated with all `CustomerProfile` TypedDict fields
- Agent elapsed time and token counts available for Audit Agent

---

## Acceptance Criteria

### AC-002-01: Demographics Correctly Retrieved
- **Given** a seeded `customers` record for `CUST-001` (John Smith)
- **When** the Customer Profile Agent runs
- **Then** `customer_profile.name = "John Smith"`, `preferred_channel = "mobile"`, `preferred_time = "morning"`, `relationship_tenure_months > 0`
- **Verified by** Phase 3 unit test with mocked `get_customer_demographics` tool

### AC-002-02: Risk Segment is One of Four Valid Values
- **Given** any customer record
- **When** `classify_risk_segment` tool returns
- **Then** `customer_profile.risk_segment` is one of: `"low"`, `"medium"`, `"high"`, `"hardship"`
- **Verified by** Phase 3 unit test checking enum constraint on output

### AC-002-03: Hardship Flag Surfaces Correctly
- **Given** customer Robert Davis (`CUST-005`) who has `hardship_flag = 1` and `hardship_reason = "medical"`
- **When** the Customer Profile Agent runs
- **Then** `customer_profile.hardship_indicators = ["medical"]` and `risk_segment = "hardship"`
- **Verified by** Phase 11 named-scenario integration test for Robert Davis

### AC-002-04: Interaction History Count Matches DB
- **Given** 2 rows in `interaction_history` for `CUST-001`
- **When** the Customer Profile Agent runs
- **Then** `customer_profile.prior_collection_interactions = 2`
- **Verified by** Phase 3 unit test with pre-seeded interaction rows

### AC-002-05: Missing Customer Returns Error Gracefully
- **Given** `customer_id = "CUST-INVALID"` which does not exist in the DB
- **When** the Customer Profile Agent runs
- **Then** agent raises `CustomerNotFoundError`; `workflow_status = "error"`; no unhandled exception reaches the API layer; HTTP response is 500 with error message
- **Verified by** Phase 3 unit test with missing customer_id

### AC-002-06: Agent Completes Within Latency Budget
- **Given** a standard customer record with 12 interaction history rows
- **When** the Customer Profile Agent runs
- **Then** agent completes in < 5 seconds (p95 target for a Sonnet Stage 1 agent)
- **Verified by** Phase 11 integration test timing + Grafana `agent_execution_duration_seconds{agent="customer_profile"}` p95

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §2.2.2 Customer Profile Agent, §5.2 `customers` + `interaction_history` schema, §6.1 Stage 1 |
| **Deployment** | Render.com FastAPI + local SQLite; Anthropic API (`llama-3.3-70b-versatile`) |
| **Observability** | `agent_execution_duration_seconds{agent="customer_profile"}` histogram; `agent_started` / `agent_complete` Loki events; `stage1.customer_profile` Tempo span |
| **SRE** | Agent error rate SLO ≤ 2%; parallel with UC-003 — slowest Stage 1 agent becomes the bottleneck; if this agent fails, pipeline status = error |
