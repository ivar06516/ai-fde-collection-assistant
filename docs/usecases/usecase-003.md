# UC-003: Build Account Profile

## Overview

| Field | Value |
|---|---|
| **ID** | UC-003 |
| **Actor** | System (Account Profile Agent triggered by Orchestrator) |
| **Goal** | Query `accounts` and `payment_history` tables to build a full account snapshot and populate `state.account_profile` |
| **Priority** | P0 |
| **Delivery Phase** | Phase 3 |
| **Pipeline Stage** | Stage 1 — parallel with UC-002 |
| **Model** | `claude-sonnet-4-6` |

---

## Preconditions

- `account_id` is present in workflow state
- SQLite DB is seeded; `accounts` and `payment_history` tables populated
- Stage 1 parallel execution started alongside UC-002

---

## Main Flow

| Step | Tool Called | DB Table | Output |
|---|---|---|---|
| 1 | `get_account_balance` | `accounts` | `outstanding_balance`, `original_balance`, `interest_rate` |
| 2 | `get_delinquency_status` | `accounts` | `days_past_due`, `account_status`, `delinquency_start` |
| 3 | `get_payment_history` | `payment_history` | last 18 months of `{month, amount_due, amount_paid, on_time}` |
| 4 | `get_linked_accounts` | `accounts` | other `account_id`s for same `customer_id` |
| 5 | `get_product_details` | `accounts` | `product_type`, `credit_limit`, `next_due_date`, `next_due_amount` |
| 6 | Returns `AccountProfile` TypedDict | — | Written to `state.account_profile` |
| 7 | SSE event emitted | — | `{"agent":"account_profile","stage":1,"status":"complete"}` |

---

## Alternative Flows

| ID | Condition | Behaviour |
|---|---|---|
| AF-01 | `account_status = "written_off"` | Profile built normally; NBA Agent will route to `flag_for_writeoff` |
| AF-02 | `account_status = "legal"` | Profile built; NBA Agent will prefer `escalate_to_legal` |
| AF-03 | Payment history < 3 months | Profile built; Arrears Prediction Agent notes low confidence in its output |
| AF-04 | `account_id` not found in DB | `AccountNotFoundError` raised; `workflow_status = "error"` |

---

## Postconditions

- `state.account_profile` populated with all `AccountProfile` TypedDict fields
- `payment_history_12m` field contains up to 18 monthly records for Arrears Prediction Agent

---

## Acceptance Criteria

### AC-003-01: Balance and DPD Retrieved Correctly
- **Given** account `ACC-001` with `outstanding_balance = 2850.00` and `days_past_due = 45` in DB
- **When** the Account Profile Agent runs
- **Then** `account_profile.outstanding_balance = 2850.00` and `account_profile.days_past_due = 45`
- **Verified by** Phase 3 unit test with known DB fixture

### AC-003-02: Payment History Contains At Least 12 Months
- **Given** an account seeded with 18 months of `payment_history` rows
- **When** the Account Profile Agent runs
- **Then** `account_profile.payment_history_12m` contains between 12 and 18 entries
- **Verified by** Phase 3 unit test asserting list length

### AC-003-03: Account Status Reflects DB Value Exactly
- **Given** accounts with each of the five statuses: `current`, `delinquent`, `legal`, `written_off`, `closed`
- **When** the Account Profile Agent runs for each
- **Then** `account_profile.account_status` matches the DB `account_status` field exactly
- **Verified by** Phase 3 parametrised unit test across all 5 status values

### AC-003-04: Payment On-Time Flag is Accurate
- **Given** a `payment_history` row with `on_time = 0` for a specific month
- **When** the Account Profile Agent runs
- **Then** the corresponding entry in `payment_history_12m` has `on_time = false`
- **Verified by** Phase 3 unit test checking on_time mapping

### AC-003-05: Written-Off Account Does Not Block Pipeline
- **Given** customer Karen Wilson (`CUST-006`) with `account_status = "written_off"`
- **When** the Account Profile Agent runs
- **Then** `state.account_profile.account_status = "written_off"`; pipeline continues to NBA Agent which returns `flag_for_writeoff`
- **Verified by** Phase 11 named-scenario integration test for Karen Wilson

### AC-003-06: DB Query Completes Within 500ms
- **Given** an account with 18 payment history rows
- **When** `get_payment_history` DB query executes
- **Then** the query completes in < 500ms
- **Verified by** Grafana `db_query_duration_seconds` metric (alert if > 500ms per `observability_strategy.md §7`)

---

## Traceability Matrix

| Dimension | Reference |
|---|---|
| **Requirements** | `REQUIREMENTS.md` §2.2.3 Account Profile Agent, §5.2 `accounts` + `payment_history` schema, §6.1 Stage 1 |
| **Deployment** | Render.com FastAPI + local SQLite; Anthropic API (`claude-sonnet-4-6`); SQLite single-writer constraint means read queries are safe in parallel with UC-002 |
| **Observability** | `agent_execution_duration_seconds{agent="account_profile"}` histogram; `db_query_duration_seconds` histogram (most expensive DB call — 18-row join); `stage1.account_profile` Tempo span |
| **SRE** | Agent error rate SLO ≤ 2%; DB query latency alert > 500ms; `payment_history` data availability is prerequisite for UC-004 (Arrears Prediction) quality |
